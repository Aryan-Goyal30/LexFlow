import { useRef, useState, type DragEvent } from 'react';
import { ExternalLink, FileText, Trash2, UploadCloud } from 'lucide-react';
import type { Case } from '../../types';
import { useCases } from '../../context/CasesContext';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { formatDate } from '../../lib/format';
import {
  ACCEPT_ATTRIBUTE,
  ACCEPTED_TYPES_LABEL,
  REJECTION_MESSAGES,
  checkFiles,
  type FileRejection,
} from '../../lib/documentFiles';

interface UploadFeedback {
  added: string[];
  rejected: FileRejection[];
}

export function DocumentsTab({ legalCase: c }: { legalCase: Case }) {
  const { addDocuments, removeDocument } = useCases();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [feedback, setFeedback] = useState<UploadFeedback | null>(null);

  // Picker and drag-and-drop both end here, so they follow the same rules.
  const attach = (fileList: FileList | null) => {
    const files = fileList ? Array.from(fileList) : [];
    if (files.length === 0) return; // cancelled picker, or a drag with no files
    const { accepted, rejected } = checkFiles(
      files,
      c.documents.map((d) => d.name),
    );
    if (accepted.length > 0) addDocuments(c.id, accepted);
    setFeedback({ added: accepted.map((f) => f.name), rejected });
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    attach(e.dataTransfer.files);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    // Moving over a child element fires dragleave too; only reset when the
    // pointer actually leaves the drop zone.
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
  };

  return (
    <div className="space-y-6">
      <div
        data-testid="document-drop-zone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-brand-200 bg-white'
        }`}
      >
        <UploadCloud className="h-9 w-9 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
        <p className="mt-3 text-sm font-medium text-brand-800">
          Drop pleadings, evidence, orders or correspondence here
        </p>
        <p className="mt-1 text-xs text-brand-500">{ACCEPTED_TYPES_LABEL}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          onClick={() => inputRef.current?.click()}
        >
          Choose files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTRIBUTE}
          className="hidden"
          aria-label="Choose files to attach"
          onChange={(e) => {
            attach(e.target.files);
            e.target.value = '';
          }}
        />
        <p className="mt-4 text-xs text-brand-400">
          Files stay in this browser tab only. They are not uploaded anywhere and are lost when the
          page is refreshed.
        </p>
      </div>

      <div role="status" aria-live="polite">
        {feedback && <UploadSummary feedback={feedback} />}
      </div>

      <Card>
        <CardHeader title={`Case Documents (${c.documents.length})`} />
        <CardBody className="p-0">
          {c.documents.length === 0 ? (
            <p className="px-5 py-6 text-sm text-brand-500">
              No documents yet. Upload the case papers to prepare this matter for analysis.
            </p>
          ) : (
            <ul className="divide-y divide-brand-100">
              {c.documents.map((doc) => (
                <li key={doc.id} className="flex items-center gap-3 px-5 py-3">
                  <span className="rounded-md bg-brand-50 p-2 text-brand-500">
                    <FileText className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-brand-900">{doc.name}</p>
                    <p className="text-xs text-brand-500">
                      {doc.type} · {doc.size} · {formatDate(doc.uploadedOn)}
                      {!doc.url && ' · sample record, no file attached'}
                    </p>
                  </div>
                  {doc.url && (
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md p-2 text-brand-500 hover:bg-brand-50 hover:text-brand-800"
                      aria-label={`Open ${doc.name}`}
                      title="Open"
                    >
                      <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => removeDocument(c.id, doc.id)}
                    className="rounded-md p-2 text-brand-400 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Remove ${doc.name}`}
                    title="Remove"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function UploadSummary({ feedback }: { feedback: UploadFeedback }) {
  const { added, rejected } = feedback;
  return (
    <div className="space-y-2">
      {added.length > 0 && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
          {added.length === 1 ? `Added ${added[0]}.` : `Added ${added.length} documents.`}
        </p>
      )}
      {rejected.length > 0 && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20">
          <p className="font-medium">
            {rejected.length === 1
              ? 'One file was not added:'
              : `${rejected.length} files were not added:`}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {rejected.map((r, i) => (
              <li key={`${i}-${r.name}`}>
                {r.name} {REJECTION_MESSAGES[r.reason]}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
