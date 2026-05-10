import React from 'react';
import { Plus, MessageSquare, PanelLeftClose } from 'lucide-react';

export interface Report {
  id: string;
  query: string;
  createdAt: string;
}

interface SidebarProps {
  reports: Report[];
  onSelect: (id: string) => void;
  currentId: string | null;
  onNew: () => void;
  onToggleCollapse: () => void;
}

export function Sidebar({ reports, onSelect, currentId, onNew, onToggleCollapse }: SidebarProps) {
  return (
    <div className="w-[260px] h-full bg-[#f8f8f5] flex flex-col border-r border-[#e8e8e3] flex-shrink-0 relative group">
      <div className="p-3 flex items-center justify-between">
        <button 
          onClick={onNew}
          className="flex-1 flex items-center justify-between px-3 py-2 text-sm font-medium hover:bg-[#eaeae6] rounded-md transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[15px] font-sans">Crypto Agent</span>
          </div>
          <Plus size={16} className="text-gray-500" />
        </button>
        <button 
          onClick={onToggleCollapse}
          className="ml-2 p-2 rounded-md hover:bg-[#eaeae6] text-gray-500 transition-colors"
          title="Close sidebar"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto mt-2 px-3">
        {reports.length > 0 && (
          <div className="text-xs font-medium text-gray-500 mb-2 px-2 mt-4">Recent Research</div>
        )}
        <div className="flex flex-col gap-0.5">
          {reports.map(report => (
            <button
              key={report.id}
              onClick={() => onSelect(report.id)}
              className={`w-full text-left px-3 py-2 text-sm rounded-md truncate transition-colors flex items-center gap-2
                ${currentId === report.id ? 'bg-[#eaeae6] text-black font-medium' : 'text-gray-700 hover:bg-[#eaeae6]'}`}
            >
              <MessageSquare size={14} className="opacity-70 flex-shrink-0" />
              <span className="truncate">{report.query}</span>
            </button>
          ))}
        </div>
      </div>
      
      <div className="p-3 border-t border-[#e8e8e3]">
        <div className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-[#eaeae6] rounded-md cursor-pointer">
          <div className="w-6 h-6 rounded-full bg-orange-200 flex items-center justify-center text-orange-800 text-xs font-medium">T</div>
          Tsin418
        </div>
      </div>
    </div>
  );
}