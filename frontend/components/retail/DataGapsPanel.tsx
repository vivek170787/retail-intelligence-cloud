import { AlertCircle } from "lucide-react";

export function DataGapsPanel({ gaps }: { gaps: string[] }) {
  if (!gaps || gaps.length === 0) return null;
  return (
    <details className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        {gaps.length} data gap{gaps.length === 1 ? "" : "s"} / uncertainty note{gaps.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {gaps.map((gap, i) => (
          <li key={i}>{gap}</li>
        ))}
      </ul>
    </details>
  );
}
