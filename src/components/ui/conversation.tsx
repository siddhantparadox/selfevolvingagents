"use client";

import { ChevronDown } from "lucide-react";
import { forwardRef } from "react";
import {
  StickToBottom,
  useStickToBottomContext,
  type StickToBottomProps,
} from "use-stick-to-bottom";
import { cn } from "@/lib/utils";

type ConversationProps = StickToBottomProps & {
  className?: string;
};

export function Conversation({
  className,
  initial = "smooth",
  resize = "smooth",
  ...props
}: ConversationProps) {
  return (
    <StickToBottom
      initial={initial}
      resize={resize}
      className={cn(
        "relative h-[560px] overflow-hidden rounded-2xl border border-white/10 bg-[#0f1116]",
        className
      )}
      {...props}
    />
  );
}

type ConversationContentProps = React.ComponentProps<typeof StickToBottom.Content>;

export function ConversationContent({
  className,
  scrollClassName,
  ...props
}: ConversationContentProps) {
  return (
    <StickToBottom.Content
      className={cn("p-6", className)}
      scrollClassName={cn("h-full overflow-y-auto", scrollClassName)}
      {...props}
    />
  );
}

type ConversationEmptyStateProps = React.HTMLAttributes<HTMLDivElement> & {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
};

export const ConversationEmptyState = forwardRef<
  HTMLDivElement,
  ConversationEmptyStateProps
>(function ConversationEmptyState(
  { className, title = "No messages yet", description, icon, children, ...props },
  ref
) {
  if (children) {
    return (
      <div ref={ref} className={className} {...props}>
        {children}
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className={cn(
        "flex min-h-[420px] flex-col items-center justify-center text-center",
        className
      )}
      {...props}
    >
      {icon ? <div className="mb-4">{icon}</div> : null}
      <p className="text-lg font-semibold text-white">{title}</p>
      {description ? <p className="mt-2 max-w-sm text-sm text-slate-400">{description}</p> : null}
    </div>
  );
});

type ConversationScrollButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement>;

export function ConversationScrollButton({
  className,
  ...props
}: ConversationScrollButtonProps) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;

  return (
    <button
      type="button"
      className={cn(
        "absolute bottom-4 left-1/2 z-20 inline-flex -translate-x-1/2 items-center justify-center rounded-full border border-white/15 bg-black/70 p-2 text-white shadow-lg transition hover:bg-black/90",
        className
      )}
      onClick={() => void scrollToBottom("smooth")}
      {...props}
    >
      <ChevronDown className="h-5 w-5" />
    </button>
  );
}
