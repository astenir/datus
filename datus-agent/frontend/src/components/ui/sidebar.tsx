import * as React from "react";

import { cn } from "@/lib/utils";

function Sidebar({ className, ...props }: React.ComponentProps<"aside">) {
  return <aside data-slot="sidebar" className={cn("sidebar", className)} {...props} />;
}

function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sidebar-header" className={cn("sidebarHeader", className)} {...props} />;
}

function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sidebar-content" className={cn("sessionPane", className)} {...props} />;
}

function SidebarGroup({ className, ...props }: React.ComponentProps<"section">) {
  return <section data-slot="sidebar-group" className={cn("sessionPane", className)} {...props} />;
}

function SidebarGroupHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sidebar-group-header" className={cn("sessionPaneHeader", className)} {...props} />;
}

function SidebarGroupContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sidebar-group-content" className={cn(className)} {...props} />;
}

export { Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupHeader, SidebarHeader };
