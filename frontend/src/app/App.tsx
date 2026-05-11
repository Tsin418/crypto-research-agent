import React, { useState } from 'react';
import { Sidebar, Report } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { PanelLeftOpen } from 'lucide-react';

interface Chat extends Report {
  report: string;
}

const RESPONSE_BODY_PREVIEW_LENGTH = 500;

function getApiBaseUrl() {
  const baseUrl = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '');

  if (import.meta.env.PROD && !baseUrl) {
    throw new Error(
      'Missing VITE_API_URL in production. Set it as a Cloudflare Pages build-time environment variable to the public FastAPI backend URL, then rebuild.'
    );
  }

  return baseUrl;
}

async function parseErrorResponse(res: Response, label: string) {
  const body = await res.text().catch(() => '');
  const bodyPreview = body ? ` ${body.slice(0, RESPONSE_BODY_PREVIEW_LENGTH)}` : '';
  return new Error(`${label}: HTTP ${res.status} ${res.statusText || ''}${bodyPreview}`);
}

function formatFetchError(error: unknown, label: string, url: string) {
  const message = error instanceof Error ? error.message : String(error);
  return new Error(`${label}: network or CORS error while requesting ${url}. ${message}`);
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const handleNewChat = () => {
    setCurrentChatId(null);
  };

  const handleSelectChat = (id: string) => {
    setCurrentChatId(id);
  };

  const currentChat = chats.find(c => c.id === currentChatId) || null;

  const handleSubmit = async (query: string) => {
    setIsLoading(true);
    setCurrentChatId(null); 

    try {
      const baseUrl = getApiBaseUrl();
      const reportEndpoint = `${baseUrl}/api/research/report`;
      const postRes = await fetch(reportEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      })
        .catch(error => {
          throw formatFetchError(error, 'Failed to start report', reportEndpoint);
        });

      if (!postRes.ok) {
        throw await parseErrorResponse(postRes, 'Failed to start report');
      }

      const { report_id } = await postRes.json();

      let reportData;
      const MAX_POLL_RETRIES = 30; // 60-second timeout
      let retries = 0;
      while (retries < MAX_POLL_RETRIES) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const statusEndpoint = `${baseUrl}/api/research/report/${report_id}`;
        const getRes = await fetch(statusEndpoint)
          .catch(error => {
            throw formatFetchError(error, 'Failed to fetch report status', statusEndpoint);
          });
        if (!getRes.ok) {
          throw await parseErrorResponse(getRes, 'Failed to fetch report status');
        }
        reportData = await getRes.json();

        if (reportData.status === 'completed' || reportData.status === 'failed') {
          break;
        }
        retries++;
      }

      if (retries >= MAX_POLL_RETRIES && reportData?.status === 'processing') {
        throw new Error('Report generation timed out after 60 seconds. Please try again.');
      }

      const reportMarkdown = reportData.status === 'completed' 
        ? reportData.report_markdown || 'Report generated but no markdown provided.'
        : `Report generation failed: ${reportData.error_message || 'Unknown error'}`;

      const newChat: Chat = {
        id: report_id,
        query,
        report: reportMarkdown,
        createdAt: new Date().toISOString()
      };
      setChats(prev => [newChat, ...prev]);
      setCurrentChatId(report_id);
    } catch (error) {
      console.error(error);
      const detail = error instanceof Error ? error.message : String(error);
      const errorChat: Chat = {
        id: Math.random().toString(36).substring(7),
        query,
        report: `**Error:** Could not generate report. Please ensure the backend is running. Details: ${detail}`,
        createdAt: new Date().toISOString()
      };
      setChats(prev => [errorChat, ...prev]);
      setCurrentChatId(errorChat.id);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#ffffff] text-[#333333] font-sans relative overflow-hidden">
      {/* Sidebar Transition */}
      <div 
        className={`transition-all duration-300 ease-in-out h-full flex-shrink-0 w-[260px] ${
          isSidebarOpen ? 'ml-0' : '-ml-[260px]'
        }`}
      >
        <Sidebar 
          reports={chats} 
          onSelect={handleSelectChat} 
          currentId={currentChatId} 
          onNew={handleNewChat}
          onToggleCollapse={() => setIsSidebarOpen(false)}
        />
      </div>

      {/* Floating Open Button */}
      {!isSidebarOpen && (
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="absolute top-4 left-4 p-2 rounded-md hover:bg-gray-100 text-gray-500 transition-colors z-10"
          title="Open sidebar"
        >
          <PanelLeftOpen size={20} />
        </button>
      )}

      <ChatArea 
        chat={currentChat} 
        onSubmit={handleSubmit} 
        isLoading={isLoading} 
      />
    </div>
  );
}
