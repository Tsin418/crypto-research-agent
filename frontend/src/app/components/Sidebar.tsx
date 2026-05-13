import {
  Activity,
  BarChart3,
  Clock3,
  Database,
  FileText,
  Plus,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import type { ResearchReport } from './dashboard/types';

interface SidebarProps {
  reports: ResearchReport[];
  currentId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
}

const navItems = [
  { label: 'Dashboard', icon: BarChart3, active: true },
  { label: 'Recent Reports', icon: Clock3 },
  { label: 'On-chain Events', icon: Activity },
  { label: 'Data Sources', icon: Database },
  { label: 'Settings', icon: Settings },
];

function formatReportMeta(report: ResearchReport) {
  const asset = report.metadata?.asset || 'Asset pending';
  const risk = report.metadata?.risk_level ? report.metadata.risk_level.replaceAll('_', ' ') : 'research';
  return `${asset} · ${risk}`;
}

export function Sidebar({ reports, currentId, onNew, onSelect }: SidebarProps) {
  return (
    <aside className="flex h-full w-[276px] shrink-0 flex-col border-r border-[#dededb] bg-[#f8f8f6]">
      <div className="border-b border-[#e4e4e1] px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-md border border-[#dededb] bg-white">
            <ShieldCheck className="size-4 text-[#2f3437]" />
          </div>
          <div>
            <div className="text-sm font-semibold text-[#14171a]">Research Desk</div>
            <div className="text-xs text-[#7a7f85]">Institutional view</div>
          </div>
        </div>
      </div>

      <div className="px-3 py-4">
        <button
          onClick={onNew}
          className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[#14171a] px-3 text-sm font-semibold text-white transition-colors hover:bg-[#2c3034]"
        >
          <Plus className="size-4" />
          New Research
        </button>
      </div>

      <nav className="space-y-1 px-3">
        {navItems.map(item => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              className={`flex h-9 w-full items-center gap-3 rounded-md px-3 text-left text-sm transition-colors ${
                item.active
                  ? 'bg-white text-[#15191d] shadow-[inset_0_0_0_1px_#e4e4e1]'
                  : 'text-[#60666c] hover:bg-white hover:text-[#15191d]'
              }`}
            >
              <Icon className="size-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="mt-6 flex-1 overflow-y-auto px-3">
        <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-[0.08em] text-[#858a90]">
          Recent Reports
        </div>
        <div className="space-y-2">
          {reports.length === 0 && (
            <div className="rounded-md border border-dashed border-[#d8d8d4] bg-white/70 px-3 py-4 text-xs leading-5 text-[#767b81]">
              Completed research reports will appear here.
            </div>
          )}

          {reports.map(report => (
            <button
              key={report.id}
              onClick={() => onSelect(report.id)}
              className={`w-full rounded-md border px-3 py-3 text-left transition-colors ${
                currentId === report.id
                  ? 'border-[#bdbfbd] bg-white'
                  : 'border-[#e2e2df] bg-white/70 hover:border-[#cfcfca] hover:bg-white'
              }`}
            >
              <div className="flex items-start gap-2">
                <FileText className="mt-0.5 size-4 shrink-0 text-[#73777d]" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-[#22262a]">{report.query}</div>
                  <div className="mt-1 truncate text-xs capitalize text-[#777d83]">{formatReportMeta(report)}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-[#e4e4e1] p-3">
        <div className="rounded-md border border-[#e0e0dd] bg-white px-3 py-2 text-xs leading-5 text-[#696f75]">
          Research only. Not financial advice or trading execution.
        </div>
      </div>
    </aside>
  );
}
