#!/usr/bin/env bash
# VillaOps AI — on-demand demo server on one EC2 instance with a fixed IP.
#
# Pay only while it runs: start it before a demo, stop it after. The Elastic IP
# (and therefore villaops.esakrissa.com) stays the same across stop/start.
#
#   ./scripts/demo.sh create     # one-time: key pair, firewall, instance, Elastic IP
#   ./scripts/demo.sh deploy     # copy code + .env to the server and (re)build the stack
#   ./scripts/demo.sh start      # power on, wait until https://$DOMAIN is healthy
#   ./scripts/demo.sh stop       # power off (disk + IP are kept)
#   ./scripts/demo.sh status     # instance state, IP, app health, auto-stop time
#   ./scripts/demo.sh extend 60  # push the auto-stop back by N minutes
#   ./scripts/demo.sh ssh        # shell on the server
#   ./scripts/demo.sh logs [svc] # follow container logs
#   ./scripts/demo.sh destroy    # delete everything (instance, disk, IP, firewall, key)
#
# Every `start` also schedules an automatic shutdown after AUTO_STOP_MIN minutes,
# so a forgotten server can't keep billing.
set -euo pipefail

PROFILE="${AWS_PROFILE:-villaops}"
REGION="${AWS_REGION:-ap-southeast-1}"
NAME="villaops-demo"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"
DISK_GB=30
DOMAIN="${DOMAIN:-villaops.esakrissa.com}"
AUTO_STOP_MIN="${AUTO_STOP_MIN:-120}"
KEY_FILE="$HOME/.ssh/${NAME}.pem"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/villaops"

# Wrappers switch errexit off around the call: with macOS bash 3.2 and the
# Homebrew aws CLI, a failing `aws` aborts the script under `set -e` even when
# the call site is guarded with `|| true`. Callers still see the exit code.
aws() {
  set +e
  command aws --profile "$PROFILE" --region "$REGION" --output text "$@"
  local rc=$?
  set -e
  return $rc
}
say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

instance_id() {
  aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' 2>/dev/null | grep -v None || true
}
instance_state() { aws ec2 describe-instances --instance-ids "$1" --query 'Reservations[0].Instances[0].State.Name'; }
eip_alloc() { aws ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].AllocationId' 2>/dev/null | grep -v None || true; }
eip_ip() { aws ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].PublicIp' 2>/dev/null | grep -v None || true; }
sg_id() { aws ec2 describe-security-groups --filters "Name=group-name,Values=$NAME" --query 'SecurityGroups[0].GroupId' 2>/dev/null | grep -v None || true; }

require_instance() {
  IID="$(instance_id)"
  [[ -n "$IID" ]] || die "No demo instance. Run: ./scripts/demo.sh create"
  IP="$(eip_ip)"
}

ssh_opts=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/${NAME}_known_hosts" -o ConnectTimeout=10)
remote() {
  set +e
  ssh "${ssh_opts[@]}" "ubuntu@$IP" "$@"
  local rc=$?
  set -e
  return $rc
}

# SSH is only open to your current public IP; refresh the rule if it changed.
allow_my_ip() {
  local sg my
  sg="$(sg_id)"; my="$(curl -fsS https://checkip.amazonaws.com | tr -d '\n')/32"
  aws ec2 authorize-security-group-ingress --group-id "$sg" \
    --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$my,Description=demo-ssh}]" >/dev/null 2>&1 || true
}

wait_ssh() {
  say "Waiting for SSH…"
  for _ in $(seq 1 60); do
    remote true 2>/dev/null && return 0
    sleep 5
  done
  die "SSH didn't come up"
}

wait_healthy() {
  local url="https://$DOMAIN/health"
  say "Waiting for $url …"
  for _ in $(seq 1 90); do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      say "✓ Live: https://$DOMAIN"
      return 0
    fi
    sleep 5
  done
  echo "Not healthy over HTTPS yet. Check DNS (A $DOMAIN → $IP) and: ./scripts/demo.sh logs caddy"
  curl -fsS --max-time 5 "http://$IP/health" >/dev/null 2>&1 && echo "(plain http://$IP/health responds)"
}

schedule_auto_stop() {
  remote "sudo shutdown -c 2>/dev/null; sudo shutdown -h +$1 'VillaOps demo auto-stop' >/dev/null 2>&1; true"
  say "Auto-stop in $1 min (around $(date -v+"$1"M '+%H:%M' 2>/dev/null || date -d "+$1 min" '+%H:%M'))."
}

cmd_create() {
  [[ -z "$(instance_id)" ]] || die "Instance already exists ($(instance_id))."
  command -v aws >/dev/null || die "AWS CLI not installed"
  aws sts get-caller-identity --query Account >/dev/null || die "Not logged in. Run: aws login --profile $PROFILE --region $REGION"

  if [[ ! -f "$KEY_FILE" ]]; then
    say "Creating key pair → $KEY_FILE"
    mkdir -p "$HOME/.ssh"
    aws ec2 create-key-pair --key-name "$NAME" --key-type ed25519 --query KeyMaterial > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
  fi

  local vpc sg ami iid alloc
  vpc="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')"
  [[ "$vpc" != "None" ]] || die "No default VPC in $REGION"
  sg="$(sg_id)"
  if [[ -z "$sg" ]]; then
    say "Creating security group (80/443 public, 22 from your IP only)"
    sg="$(aws ec2 create-security-group --group-name "$NAME" --description "VillaOps demo" --vpc-id "$vpc" --query GroupId)"
    for port in 80 443; do
      aws ec2 authorize-security-group-ingress --group-id "$sg" --protocol tcp --port "$port" --cidr 0.0.0.0/0 >/dev/null
    done
  fi
  allow_my_ip

  ami="$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value)"
  say "Launching $INSTANCE_TYPE (Ubuntu 24.04, ${DISK_GB} GB gp3) in $REGION"
  iid="$(aws ec2 run-instances \
    --image-id "$ami" --instance-type "$INSTANCE_TYPE" --key-name "$NAME" --security-group-ids "$sg" \
    --instance-initiated-shutdown-behavior stop \
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3,DeleteOnTermination=true}" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" "ResourceType=volume,Tags=[{Key=Name,Value=$NAME}]" \
    --user-data "$(cat <<'USERDATA'
#!/bin/bash
set -e
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
mkdir -p /opt/villaops && chown ubuntu:ubuntu /opt/villaops
touch /var/lib/cloud/instance/villaops-ready
USERDATA
)" \
    --query 'Instances[0].InstanceId')"
  command aws --profile "$PROFILE" --region "$REGION" ec2 wait instance-running --instance-ids "$iid"

  alloc="$(eip_alloc)"
  if [[ -z "$alloc" ]]; then
    alloc="$(aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" --query AllocationId)"
  fi
  aws ec2 associate-address --instance-id "$iid" --allocation-id "$alloc" >/dev/null
  IP="$(eip_ip)"
  say "✓ Instance $iid with fixed IP $IP"
  echo
  echo "Next:"
  echo "  1. Cloudflare DNS: A record  ${DOMAIN%%.*}  →  $IP  (DNS only / grey cloud)"
  echo "  2. ./scripts/demo.sh deploy"
}

cmd_deploy() {
  require_instance
  [[ "$(instance_state "$IID")" == "running" ]] || die "Instance is not running. Run: ./scripts/demo.sh start"
  allow_my_ip
  wait_ssh
  say "Waiting for Docker install (first boot)…"
  for _ in $(seq 1 60); do remote "test -f /var/lib/cloud/instance/villaops-ready && docker info >/dev/null 2>&1" && break; sleep 5; done

  say "Syncing code → $IP:$REMOTE_DIR"
  rsync -az --delete -e "ssh ${ssh_opts[*]}" \
    --exclude .git --exclude node_modules --exclude .next --exclude .venv --exclude venv \
    --exclude __pycache__ --exclude .ruff_cache --exclude .pytest_cache --exclude .idea --exclude .cursor \
    --exclude .DS_Store --exclude .claude --exclude .aws --exclude .mcp.json --exclude .env \
    --exclude checkpoints --exclude todos --exclude prompts --exclude screenshots --exclude demos \
    --exclude PLAN.md --exclude NOTE.md --exclude WORKFLOW.md --exclude COST_AND_COMPUTE.md \
    "$REPO_ROOT/" "ubuntu@$IP:$REMOTE_DIR/"
  # .env goes over SSH only; never into the image or git
  scp "${ssh_opts[@]}" -q "$REPO_ROOT/.env" "ubuntu@$IP:$REMOTE_DIR/.env"
  remote "chmod 600 $REMOTE_DIR/.env"

  say "Building and starting the stack (first build takes ~10 min)…"
  remote "cd $REMOTE_DIR && DOMAIN=$DOMAIN docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans"
  say "Running migrations"
  remote "cd $REMOTE_DIR && docker compose exec -T backend alembic upgrade head"
  if ! remote "cd $REMOTE_DIR && docker compose exec -T postgres psql -U villa -d villa_ops -tAc \"select 1 from users where email='demo@villaops.ai'\"" | grep -q 1; then
    say "Seeding demo data (demo@villaops.ai)"
    remote "cd $REMOTE_DIR && docker compose exec -T backend python scripts/seed_data.py"
  fi
  remote "docker image prune -f >/dev/null"
  schedule_auto_stop "$AUTO_STOP_MIN"
  wait_healthy
}

cmd_start() {
  require_instance
  local state; state="$(instance_state "$IID")"
  if [[ "$state" != "running" ]]; then
    [[ "$state" == "stopping" ]] && command aws --profile "$PROFILE" --region "$REGION" ec2 wait instance-stopped --instance-ids "$IID"
    say "Starting $IID…"
    aws ec2 start-instances --instance-ids "$IID" >/dev/null
    command aws --profile "$PROFILE" --region "$REGION" ec2 wait instance-running --instance-ids "$IID"
  fi
  allow_my_ip
  wait_ssh
  schedule_auto_stop "$AUTO_STOP_MIN"
  wait_healthy
}

cmd_stop() {
  require_instance
  say "Stopping $IID (disk and IP $IP are kept)…"
  aws ec2 stop-instances --instance-ids "$IID" >/dev/null
  command aws --profile "$PROFILE" --region "$REGION" ec2 wait instance-stopped --instance-ids "$IID"
  say "✓ Stopped. Compute billing paused."
}

cmd_status() {
  require_instance
  local state; state="$(instance_state "$IID")"
  echo "Instance : $IID ($INSTANCE_TYPE, $REGION) — $state"
  echo "Fixed IP : ${IP:-none}"
  echo "DNS      : $DOMAIN → $(dig +short "$DOMAIN" 2>/dev/null | tail -1)"
  if [[ "$state" == "running" ]]; then
    curl -fsS --max-time 5 "https://$DOMAIN/health" >/dev/null 2>&1 && echo "App      : ✓ https://$DOMAIN" || echo "App      : ✗ not responding on https://$DOMAIN"
    allow_my_ip
    local at; at="$(remote "cat /run/systemd/shutdown/scheduled 2>/dev/null | sed -n 's/^USEC=//p'" 2>/dev/null || true)"
    [[ -n "$at" ]] && echo "Auto-stop: $(date -r $((at / 1000000)) '+%a %H:%M' 2>/dev/null || date -d @$((at / 1000000)) '+%a %H:%M')"
  fi
}

cmd_extend() { require_instance; allow_my_ip; schedule_auto_stop "${1:-60}"; }
cmd_ssh() { require_instance; allow_my_ip; ssh "${ssh_opts[@]}" "ubuntu@$IP"; }
cmd_logs() { require_instance; allow_my_ip; remote "cd $REMOTE_DIR && docker compose logs -f --tail 100 ${1:-}"; }

cmd_destroy() {
  local iid alloc sg
  iid="$(instance_id)"; alloc="$(eip_alloc)"; sg="$(sg_id)"
  echo "This permanently deletes: instance ${iid:-–}, its disk (database!), Elastic IP $(eip_ip), security group, key pair."
  read -r -p "Type 'destroy' to continue: " ok
  [[ "$ok" == "destroy" ]] || die "Aborted"
  if [[ -n "$iid" ]]; then
    say "Terminating $iid"
    aws ec2 terminate-instances --instance-ids "$iid" >/dev/null
    command aws --profile "$PROFILE" --region "$REGION" ec2 wait instance-terminated --instance-ids "$iid"
  fi
  [[ -n "$alloc" ]] && { say "Releasing Elastic IP"; aws ec2 release-address --allocation-id "$alloc"; }
  [[ -n "$sg" ]] && { say "Deleting security group"; aws ec2 delete-security-group --group-id "$sg"; }
  aws ec2 delete-key-pair --key-name "$NAME" >/dev/null 2>&1 || true
  rm -f "$KEY_FILE" "$HOME/.ssh/${NAME}_known_hosts"
  say "✓ Everything deleted. Remember to remove the Cloudflare A record for $DOMAIN."
}

case "${1:-}" in
  create) cmd_create ;;
  deploy) cmd_deploy ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  extend) cmd_extend "${2:-60}" ;;
  ssh) cmd_ssh ;;
  logs) cmd_logs "${2:-}" ;;
  destroy) cmd_destroy ;;
  *) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
