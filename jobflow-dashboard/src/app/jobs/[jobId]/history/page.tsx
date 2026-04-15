import Link from "next/link";
import HistoryViewer from "@/components/HistoryViewer";

export default async function HistoryPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b px-4 py-3 flex items-center gap-3">
        <Link href={`/jobs/${jobId}`} className="text-gray-500 hover:text-gray-700 text-sm">
          ← Job 상세
        </Link>
        <h1 className="text-base font-bold text-gray-800">변경 히스토리</h1>
      </header>
      <main className="flex-1 p-4 md:p-6 overflow-x-auto">
        <HistoryViewer jobId={jobId} />
      </main>
    </div>
  );
}
