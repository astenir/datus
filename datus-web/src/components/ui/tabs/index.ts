import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Tabs } from "./Tabs.vue"
export { default as TabsContent } from "./TabsContent.vue"
export { default as TabsList } from "./TabsList.vue"
export { default as TabsTrigger } from "./TabsTrigger.vue"

export const tabsListVariants = cva(
  'group/tabs-list inline-flex w-fit items-center justify-center text-muted-foreground data-[orientation=vertical]:h-fit data-[orientation=vertical]:flex-col',
  {
    variants: {
      variant: {
        default: 'gap-0.5 rounded-4xl border border-border/60 bg-muted/50 p-0.5 shadow-none data-[orientation=horizontal]:h-9',
        line: 'gap-1 rounded-none border-0 bg-transparent p-0',
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export type TabsListVariants = VariantProps<typeof tabsListVariants>
