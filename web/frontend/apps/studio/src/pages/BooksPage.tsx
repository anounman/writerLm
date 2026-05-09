import React from "react";
import { Download, FileCode2, BookOpen, Calendar } from "lucide-react";
import { Button } from "@writerlm/ui";
import { ApiClient, GeneratedBook, friendlyApiErrorMessage } from "../api";

interface BooksPageProps {
  api: ApiClient;
  books: GeneratedBook[];
  onNotice: (message: string) => void;
}

export function BooksPage({ api, books, onNotice }: BooksPageProps) {
  async function download(book: GeneratedBook, artifact: string) {
    try {
      const { blob, filename } = await api.downloadArtifact(book.id, artifact);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { onNotice(friendlyApiErrorMessage(e, "Download failed.")); }
  }

  return (
    <div className="px-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-border">
        <h2 className="text-base font-semibold text-foreground">Library</h2>
        <span className="text-xs font-mono text-muted-foreground">{books.length} artifact{books.length !== 1 ? "s" : ""}</span>
      </div>

      {books.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 border-2 border-dashed border-border rounded-xl text-center">
          <BookOpen size={32} className="text-muted-foreground/30 mb-4" />
          <p className="text-sm font-medium text-muted-foreground">No books generated yet</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Run a pipeline to generate your first book</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {books.map(book => (
            <div key={book.id} className="group rounded-xl border border-border bg-card hover:border-muted-foreground/40 transition-colors">
              {/* Card header */}
              <div className="p-5">
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center flex-none">
                    <BookOpen size={15} className="text-muted-foreground" />
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <Calendar size={10} />
                    {new Date(book.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </div>
                </div>
                <h3 className="text-sm font-semibold text-foreground mb-1 line-clamp-2 leading-snug">{book.title}</h3>
                <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{book.topic}</p>
              </div>

              {/* Actions */}
              <div className="px-5 pb-5 flex gap-2">
                <Button variant="outline" size="sm" className="flex-1 text-xs" disabled={!book.pdf_path} onClick={() => download(book, "pdf")}>
                  <Download size={12} /> PDF
                </Button>
                <Button variant="outline" size="sm" className="flex-1 text-xs" disabled={!book.latex_path} onClick={() => download(book, "latex")}>
                  <FileCode2 size={12} /> LaTeX
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
