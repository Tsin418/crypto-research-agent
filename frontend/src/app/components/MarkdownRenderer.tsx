import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-slate max-w-none text-base leading-relaxed break-words
      prose-p:my-4 prose-p:leading-7 
      prose-headings:font-semibold prose-headings:mb-4 prose-headings:mt-8
      prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
      prose-ul:list-disc prose-ul:pl-6 prose-ul:my-4 prose-ul:marker:text-gray-400
      prose-ol:list-decimal prose-ol:pl-6 prose-ol:my-4
      prose-li:my-1
      prose-pre:bg-[#1e1e1e] prose-pre:text-white prose-pre:p-4 prose-pre:rounded-lg prose-pre:my-6 prose-pre:overflow-x-auto
      prose-code:bg-gray-100 prose-code:text-gray-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:text-sm prose-code:font-mono
      prose-a:text-blue-600 prose-a:underline prose-a:underline-offset-2 hover:prose-a:text-blue-800
      prose-blockquote:border-l-4 prose-blockquote:border-gray-200 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:text-gray-600
      prose-table:w-full prose-table:border-collapse prose-table:my-6
      prose-th:border prose-th:border-gray-200 prose-th:px-4 prose-th:py-2 prose-th:bg-gray-50 prose-th:text-left
      prose-td:border prose-td:border-gray-200 prose-td:px-4 prose-td:py-2"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}