import { AlertTriangle } from "lucide-react";

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-red-50 px-3 py-2.5 text-sm text-red-700">
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
