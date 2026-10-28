/**
 * Single source of truth for the sidebar's three logical groups. `enabled`
 * marks the two workspaces wired to real data in this increment --
 * everything else renders a honest "Coming soon" placeholder rather than
 * fabricated data (see components/retail/ComingSoonCard.tsx).
 */

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Database,
  FileClock,
  Gauge,
  Heart,
  LayoutDashboard,
  MessageSquare,
  Package,
  RefreshCw,
  Settings,
  ShieldCheck,
  Tag,
  Truck,
  Users,
  Wallet,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  enabled: boolean;
  comingSoonNote?: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Workspace",
    items: [
      { label: "Executive Overview", href: "/", icon: LayoutDashboard, enabled: true },
      {
        label: "Inventory Intelligence",
        href: "/inventory",
        icon: Package,
        enabled: true,
      },
      {
        label: "Demand Forecasting",
        href: "/demand",
        icon: BarChart3,
        enabled: true,
      },
      {
        label: "Replenishment",
        href: "/replenishment",
        icon: RefreshCw,
        enabled: true,
      },
      {
        label: "Promotion Intelligence",
        href: "/promotions",
        icon: Tag,
        enabled: true,
      },
      {
        label: "Order Fulfillment",
        href: "/fulfillment",
        icon: Truck,
        enabled: true,
      },
      {
        label: "Customer Experience",
        href: "/customer-experience",
        icon: Heart,
        enabled: true,
      },
    ],
  },
  {
    title: "AI Intelligence",
    items: [
      { label: "Ask Retail AI", href: "/ask-retail-ai", icon: MessageSquare, enabled: true },
      {
        label: "Agent Monitoring",
        href: "/agent-monitoring",
        icon: Activity,
        enabled: true,
      },
      {
        label: "Agent Execution History",
        href: "/agent-history",
        icon: FileClock,
        enabled: true,
      },
    ],
  },
  {
    title: "Data & Administration",
    items: [
      {
        label: "Data Sources & Integrations",
        href: "/data-sources",
        icon: Database,
        enabled: true,
      },
      {
        label: "Data Quality",
        href: "/data-quality",
        icon: Gauge,
        enabled: true,
      },
      {
        label: "Audit Log",
        href: "/audit-log",
        icon: ShieldCheck,
        enabled: true,
      },
      {
        label: "Subscription & Usage",
        href: "/subscription",
        icon: Wallet,
        enabled: true,
      },
      {
        label: "User Management",
        href: "/users",
        icon: Users,
        enabled: true,
      },
      {
        label: "Settings",
        href: "/settings",
        icon: Settings,
        enabled: true,
      },
    ],
  },
];
