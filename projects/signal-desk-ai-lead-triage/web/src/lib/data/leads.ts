import { qualifyLead } from "@/lib/ai/qualifier";

export type SampleLead = {
  id: string;
  name: string;
  company: string;
  service: string;
  budget: string;
  timeline: string;
  source: string;
  status: "New" | "In review" | "Follow-up";
  created: string;
  description: string;
};

// These records are invented examples; they are not real prospects or customer data.
export const sampleLeads: SampleLead[] = [
  {
    id: "northline",
    name: "Della Kim",
    company: "Northline Objects",
    service: "Shopify redesign",
    budget: "$8,000",
    timeline: "Within 6 weeks",
    source: "Website form",
    status: "New",
    created: "09:14",
    description: "We're a small home goods brand and want to redo our Shopify checkout before our autumn launch. The founder approved an $8,000 budget. Our main goal is fewer abandoned carts; we'd like to book a discovery call this week.",
  },
  {
    id: "fieldnotes",
    name: "Amir Joseph",
    company: "Fieldnote Press",
    service: "Brand identity",
    budget: "$6,500",
    timeline: "Within 4 weeks",
    source: "Referral",
    status: "In review",
    created: "08:42",
    description: "Our director has signed off on $6,500 for a brand identity and a landing page for our new editorial series. The scope is set and we need the first version in four weeks. Please send a quote.",
  },
  {
    id: "hushwell",
    name: "Kei Nakamura",
    company: "Hushwell Coffee",
    service: "Ecommerce",
    budget: "Not stated",
    timeline: "Exploring",
    source: "Email",
    status: "Follow-up",
    created: "Yesterday",
    description: "We might want to do something with our site sometime. I am exploring options, not sure what we need yet, and may ask the owner about it next year. There is no budget decided.",
  },
  {
    id: "juniper",
    name: "Nadia Sol",
    company: "Juniper & Tide",
    service: "Website refresh",
    budget: "No budget yet",
    timeline: "By tomorrow",
    source: "Social",
    status: "New",
    created: "Yesterday",
    description: "This is a student portfolio project for exposure. Could you build a full website by tomorrow for free? I don't have a budget or an approved scope yet.",
  },
];

export function getLeadById(id: string) {
  return sampleLeads.find((lead) => lead.id === id);
}

export function getLeadSummaries() {
  return sampleLeads.map((lead) => ({ ...lead, score: qualifyLead(lead).score }));
}
