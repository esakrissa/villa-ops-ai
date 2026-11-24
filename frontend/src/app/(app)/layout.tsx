"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Header } from "@/components/ui/Header";
import { Sidebar } from "@/components/ui/Sidebar";
import { usePersistentState } from "@/lib/hooks/usePersistentState";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = usePersistentState("villaops.sidebar.collapsed", false);
  const isChat = usePathname().startsWith("/chat");

  return (
    <div className="flex h-dvh overflow-hidden bg-cream">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
      />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* The chat page draws its own top bar; keep the mobile menu there too */}
        <Header onMenuToggle={() => setSidebarOpen(!sidebarOpen)} mobileOnly={isChat} />
        <main className={isChat ? "min-h-0 flex-1 overflow-hidden" : "flex-1 overflow-y-auto bg-gray-50 p-4 md:p-8"}>
          {children}
        </main>
      </div>
    </div>
  );
}
