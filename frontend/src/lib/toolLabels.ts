/** Human-readable labels for the agent's MCP tools — shown as live steps. */
const LABELS: Record<string, { running: string; done: string }> = {
  booking_search: { running: "Searching bookings", done: "Searched bookings" },
  booking_create: { running: "Creating booking", done: "Created booking" },
  booking_update: { running: "Updating booking", done: "Updated booking" },
  booking_analytics: { running: "Crunching occupancy", done: "Analysed occupancy" },
  guest_lookup: { running: "Looking up guest", done: "Looked up guest" },
  guest_create: { running: "Adding guest", done: "Added guest" },
  guest_update: { running: "Updating guest", done: "Updated guest" },
  guest_delete: { running: "Removing guest", done: "Removed guest" },
  property_list: { running: "Listing properties", done: "Listed properties" },
  property_create: { running: "Creating property", done: "Created property" },
  property_update: { running: "Updating property", done: "Updated property" },
  property_manage: { running: "Managing property", done: "Managed property" },
  property_delete: { running: "Removing property", done: "Removed property" },
  send_notification: { running: "Sending notification", done: "Sent notification" },
  booking_search_hotels: { running: "Searching Booking.com", done: "Searched Booking.com" },
  booking_hotel_details: { running: "Opening Booking.com hotel", done: "Opened Booking.com hotel" },
  airbnb_search: { running: "Searching Airbnb", done: "Searched Airbnb" },
  airbnb_listing_details: { running: "Opening Airbnb listing", done: "Opened Airbnb listing" },
  tripadvisor_search_nearby_locations: { running: "Finding places on Tripadvisor", done: "Found places on Tripadvisor" },
  tripadvisor_search_locations: { running: "Searching Tripadvisor", done: "Searched Tripadvisor" },
  tripadvisor_get_location_details: { running: "Opening Tripadvisor place", done: "Opened Tripadvisor place" },
  web_search_exa: { running: "Searching the web", done: "Searched the web" },
  web_fetch_exa: { running: "Reading web page", done: "Read web page" },
};

export function humanizeToolName(name: string): string {
  const words = name.replace(/_exa$/, "").split("_");
  return words.map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");
}

export function toolLabel(name: string, running: boolean): string {
  const entry = LABELS[name];
  if (entry) return running ? entry.running : entry.done;
  return humanizeToolName(name);
}

/** Short, user-facing summary of a tool call's arguments (hides user_id). */
export function summarizeArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([k, v]) => k !== "user_id" && v !== null && v !== undefined && v !== "")
    .slice(0, 3)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" · ");
}
