import { Footer } from "@/components/layout/Footer";

export function PlaceholderDocPage(props: {
  headline: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <main className="flex-grow px-6 py-16 max-w-xl mx-auto">
        <h1 className="text-2xl font-semibold text-slate-900 mb-4">{props.headline}</h1>
        <div className="text-slate-600 leading-relaxed space-y-4">{props.children}</div>
      </main>
      <Footer />
    </div>
  );
}
