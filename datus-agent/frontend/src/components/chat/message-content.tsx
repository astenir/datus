import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "@/types";

import { ToolCard } from "./tool-card";

function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ children, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer">
            {children}
          </a>
        )
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export function MessageContent({ message }: { message: ChatMessage }) {
  const blocks = message.blocks?.length ? message.blocks : [{ type: "markdown" as const, content: message.content }];
  return (
    <div className="messageBlocks">
      {blocks.map((block, index) => {
        if (block.type === "tool-call") {
          return <ToolCard key={index} mode="call" toolName={block.toolName} value={block.params} />;
        }
        if (block.type === "tool-result") {
          return (
            <ToolCard
              key={index}
              mode="result"
              toolName={block.toolName}
              value={block.result}
              duration={block.duration}
              shortDesc={block.shortDesc}
            />
          );
        }
        return (
          <div className="markdownBody" key={index}>
            <MarkdownMessage content={block.content} />
          </div>
        );
      })}
    </div>
  );
}
