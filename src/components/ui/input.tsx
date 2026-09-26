import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(({ className, ...props }, ref) => (
  <input className={cn("field-input", className)} ref={ref} {...props} />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(({ className, ...props }, ref) => (
  <textarea className={cn("field-input field-textarea", className)} ref={ref} {...props} />
));
Textarea.displayName = "Textarea";
