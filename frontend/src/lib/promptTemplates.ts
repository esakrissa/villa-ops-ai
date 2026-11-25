/**
 * Prompt templates shown in the composer (text chat) and in Villa's voice mode.
 * Clicking one sends it as the user's message; in voice mode Villa answers out loud.
 */
export interface PromptTemplate {
  title: string;
  prompt: string;
}

export interface TemplateGroup {
  id: string;
  label: string;
  templates: PromptTemplate[];
}

export const TEMPLATE_GROUPS: TemplateGroup[] = [
  {
    id: "trip",
    label: "Trip planning",
    templates: [
      { title: "A week in Ubud", prompt: "Plan a relaxed one-week holiday in Ubud for two people, mid-range budget." },
      { title: "Foodie weekend", prompt: "Plan a three-day foodie weekend in Ubud. Where should we eat?" },
      { title: "Top attractions", prompt: "What are the top-rated attractions around Ubud?" },
      { title: "Restaurants nearby", prompt: "Find highly rated restaurants in central Ubud." },
      { title: "Where to stay", prompt: "Suggest a few well-reviewed places to stay in Ubud." },
      { title: "Hotel prices", prompt: "What do Booking.com hotels in Ubud cost for two nights next weekend?" },
      { title: "Weather this month", prompt: "What's the weather usually like in Ubud this time of year?" },
    ],
  },
  {
    id: "ops",
    label: "Operations",
    templates: [
      { title: "Today's check-ins", prompt: "Who is checking in today?" },
      { title: "Arrivals this week", prompt: "Which guests are arriving in the next 7 days?" },
      { title: "Occupancy this month", prompt: "What's the occupancy rate this month?" },
      { title: "Revenue by villa", prompt: "Show revenue and occupancy for each of my villas this month." },
      { title: "Pending bookings", prompt: "Which bookings are still pending?" },
      { title: "Availability", prompt: "Is any of my villas free next weekend?" },
    ],
  },
  {
    id: "guests",
    label: "Guests",
    templates: [
      { title: "Find a guest", prompt: "Look up guest Sarah Chen and her bookings." },
      { title: "Special requests", prompt: "Which upcoming bookings have special requests?" },
      { title: "Repeat guests", prompt: "Who are my repeat guests?" },
    ],
  },
  {
    id: "market",
    label: "Market",
    templates: [
      { title: "Compare with Airbnb", prompt: "Compare my villa prices with similar Airbnb villas in Ubud." },
      { title: "Competitor hotels", prompt: "How do Booking.com hotels in Ubud price next weekend compared with my villas?" },
    ],
  },
  {
    id: "policies",
    label: "Policies",
    templates: [
      { title: "Cancellation policy", prompt: "What's our cancellation policy?" },
      { title: "Check-in times", prompt: "What are our check-in and check-out times?" },
      { title: "Pets and smoking", prompt: "Can guests bring pets or smoke in the villas?" },
      { title: "Guest data", prompt: "How long do we keep guest personal data?" },
      { title: "Our documents", prompt: "Which documents are in the knowledge base?" },
    ],
  },
];

/** Voice mode leads with trip planning (Villa's concierge use case). */
export const VOICE_GROUP_ORDER = ["trip", "ops", "policies", "guests", "market"];
export const TEXT_GROUP_ORDER = ["ops", "trip", "guests", "market", "policies"];

export function orderedGroups(order: string[]): TemplateGroup[] {
  return order.map((id) => TEMPLATE_GROUPS.find((g) => g.id === id)).filter((g): g is TemplateGroup => !!g);
}
