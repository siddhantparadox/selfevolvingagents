"use client";

import { ChevronDown, Flame } from "lucide-react";
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
        "glass-panel relative h-[560px] overflow-hidden rounded-3xl",
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
      className={cn("p-4 sm:p-6", className)}
      scrollClassName={cn("soft-scroll h-full overflow-y-auto", scrollClassName)}
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
      <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-white/5 text-[color:var(--primary)] shadow-[0_6px_20px_rgba(4,7,12,0.35)]">
        {icon ?? <Flame className="h-6 w-6" />}
      </div>
      <p className="font-display text-2xl font-semibold text-[color:var(--foreground)]">{title}</p>
      {description ? (
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-[color:var(--muted-foreground)]">
          {description}
        </p>
      ) : null}
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
        "absolute bottom-4 left-1/2 z-20 inline-flex -translate-x-1/2 items-center justify-center rounded-full border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)]/95 p-2 text-[color:var(--foreground)] shadow-[0_10px_22px_rgba(7,11,18,0.42)] transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--background)]",
        className
      )}
      onClick={() => void scrollToBottom("smooth")}
      {...props}
    >
      <ChevronDown className="h-5 w-5" />
    </button>
  );
}
