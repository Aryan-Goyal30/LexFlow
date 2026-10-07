import { useRef, useState, type DragEvent } from 'react';
import { ExternalLink, FileText, Trash2, UploadCloud } from 'lucide-react';
import type { Case } from '../../types';
import { useCases } from '../../context/CasesContext';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { formatDate } from '../../lib/format';

const ACCEPT = '.pdf,.doc,.docx,.txt,image/*';

export function DocumentsTab({ legalCase: c }: { legalCase: Case }) {
  const { addDocuments, removeDocument } = useCases();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const upload = (files: FileList | null) => {
    if (files && files.length > 0) addDocuments(c.id, Array.from(files));
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files);
  };

  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-brand-200 bg-white'
        }`}
      >
        <UploadCloud className="h-9 w-9 text-brand-300" strokeWidth={1.5} />
        <p className="mt-3 text-sm font-medium text-brand-800">
          Drop pleadings, evidence, orders or correspondence here
        </p>
        <p className="mt-1 text-xs text-brand-500">PDF, Word, text or images</p>
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => inputRef.current?.click()}>
          Choose files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            upload(e.target.files);
            e.target.value = '';
          }}
        />
        <p className="mt-4 text-xs text-brand-400">
          Files stay in this browser session only — there is no file storage yet.
        </p>
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
                    <FileText className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-brand-900">{doc.name}</p>
                    <p className="text-xs text-brand-500">
                      {doc.type} · {doc.size} · {formatDate(doc.uploadedOn)}
                      {!doc.url && ' · record only'}
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
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => removeDocument(c.id, doc.id)}
                    className="rounded-md p-2 text-brand-400 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Remove ${doc.name}`}
                    title="Remove"
                  >
                    <Trash2 className="h-4 w-4" />
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
