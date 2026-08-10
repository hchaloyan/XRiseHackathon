import { AskBar } from './sections/AskBar';
import InsightHeader from './sections/InsightHeader';
import KpiGrid from './sections/KpiGrid';
import EventTable from './sections/EventTable';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <AskBar />
      <div className="max-w-7xl mx-auto p-6">
        <InsightHeader />
        <div className="mt-8">
          <KpiGrid />
        </div>
        <div className="mt-8">
          <EventTable />
        </div>
      </div>
    </div>
  );
}