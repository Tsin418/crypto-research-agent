import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Paperclip, Mic } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { Report } from './Sidebar';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatAreaProps {
  chat: { id: string, query: string, report: string } | null;
  onSubmit: (query: string) => void;
  isLoading: boolean;
}

export function ChatArea({ chat, onSubmit, isLoading }: ChatAreaProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSubmit(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const isHome = !chat && !isLoading;

  return (
    <div className="flex-1 flex flex-col h-full bg-white relative">
      <div className="flex-1 overflow-y-auto">
        {isHome ? (
          <div className="h-full flex flex-col items-center justify-center max-w-3xl mx-auto px-4">
            <h1 className="text-3xl font-semibold mb-8 text-[#2d2d2d]">What crypto research do you need?</h1>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-8 pb-32 flex flex-col gap-6">
            {chat && (
              <>
                <div className="flex justify-end">
                  <div className="bg-[#f3f3ee] text-[#2d2d2d] px-5 py-3 rounded-2xl max-w-[85%] text-[15px] leading-relaxed">
                    {chat.query}
                  </div>
                </div>
                
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-lg bg-[#d9d7ce] flex-shrink-0 flex items-center justify-center overflow-hidden">
                    <span className="text-xl">🤖</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <MarkdownRenderer content={chat.report} />
                  </div>
                </div>
              </>
            )}
            
            {isLoading && (
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-lg bg-[#d9d7ce] flex-shrink-0 flex items-center justify-center overflow-hidden animate-pulse">
                  <span className="text-xl">🤖</span>
                </div>
                <div className="flex-1 py-1">
                  <div className="h-4 bg-gray-200 rounded w-1/3 animate-pulse mb-2"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/4 animate-pulse"></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className={`absolute bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-10 pb-6 px-4
        ${isHome ? 'top-1/2 -mt-4 flex flex-col justify-start pb-0 pt-0 bg-none' : ''}`}>
        <div className="max-w-3xl mx-auto w-full relative">
          <form 
            onSubmit={handleSubmit}
            className="relative flex flex-col bg-[#f4f4f4] rounded-2xl border border-gray-200 focus-within:border-gray-300 focus-within:ring-1 focus-within:ring-gray-300 transition-all shadow-sm"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Analyze why BTC dropped today..."
              className="w-full bg-transparent resize-none outline-none py-3 px-4 min-h-[56px] max-h-[200px] text-[#2d2d2d] text-[15px]"
              rows={1}
            />
            <div className="flex justify-between items-center px-3 py-2 text-gray-400">
              <div className="flex items-center gap-1">
                <button type="button" className="p-1.5 hover:text-gray-600 rounded-md hover:bg-gray-200/50 transition-colors">
                  <Paperclip size={18} />
                </button>
              </div>
              <button 
                type="submit"
                disabled={!input.trim() || isLoading}
                className={`p-1.5 rounded-lg transition-colors flex items-center justify-center ${
                  input.trim() && !isLoading 
                    ? 'bg-black text-white hover:bg-gray-800' 
                    : 'bg-[#e5e5e5] text-gray-400'
                }`}
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </form>
          {isHome && (
             <div className="flex flex-wrap gap-2 mt-4 justify-center text-sm text-gray-500 max-w-2xl mx-auto">
                <button onClick={() => onSubmit("What caused the recent ETH gas spike?")} className="px-4 py-2 bg-white hover:bg-[#f8f8f8] rounded-full transition-colors border border-gray-200 shadow-sm text-gray-600">Recent ETH gas spike</button>
                <button onClick={() => onSubmit("Summarize latest DeFiLlama stablecoin flows.")} className="px-4 py-2 bg-white hover:bg-[#f8f8f8] rounded-full transition-colors border border-gray-200 shadow-sm text-gray-600">DeFiLlama stablecoin flows</button>
                <button onClick={() => onSubmit("Analyze BTC options put-call ratio.")} className="px-4 py-2 bg-white hover:bg-[#f8f8f8] rounded-full transition-colors border border-gray-200 shadow-sm text-gray-600">BTC options put-call ratio</button>
             </div>
          )}
        </div>
        {!isHome && <div className="text-center text-xs text-gray-400 mt-3">Crypto Research Agent can make mistakes. Please verify important information.</div>}
      </div>
    </div>
  );
}