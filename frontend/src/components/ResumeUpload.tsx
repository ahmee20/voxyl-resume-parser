import React, { useEffect, useRef, useState } from 'react';
import { UploadCloud, FileCheck, AlertCircle, Loader2 } from 'lucide-react';
import { resumeApi } from '../services/api';
import type { Resume } from '../types/api';

interface ResumeUploadProps {
  onUploadSuccess: (resume: Resume) => void;
}

export const ResumeUpload: React.FC<ResumeUploadProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedResume, setSavedResume] = useState<Resume | null>(null);
  const [showUploader, setShowUploader] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const loadSavedResume = async () => {
      try {
        const latest = await resumeApi.getLatestResume();
        if (latest) {
          setSavedResume(latest);
          onUploadSuccess(latest);
        }
      } catch {
        // ignore
      }
    };

    void loadSavedResume();
  }, []);

  const handleFile = async (file: File) => {
    setError(null);
    const validExtensions = ['.pdf', '.docx'];
    const hasValidExt = validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext));

    if (!hasValidExt) {
      setError('Please upload a valid .pdf or .docx document.');
      return;
    }

    try {
      setIsUploading(true);
      const resume = await resumeApi.uploadResume(file);
      setSavedResume(resume);
      setShowUploader(false);
      onUploadSuccess(resume);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to upload and parse resume.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="rounded-[32px] px-6 py-6">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="hero-type text-base font-semibold text-primary-600">Resume upload</h2>
          <p className="text-xs text-slate-500">
            Add a PDF or DOCX. Voxyl keeps it private and brings it back the next time you sign in.
          </p>
        </div>
        {savedResume && (
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700">
            <FileCheck className="w-3.5 h-3.5" />
            <span>Saved</span>
          </div>
        )}
      </div>

      {savedResume && !showUploader ? (
        <div className="rounded-[26px] bg-white/55 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Current resume
              </p>
              <p className="mt-1 text-sm font-semibold text-primary-600">
                {savedResume.filename || `Resume v${savedResume.version}`}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Version {savedResume.version} is ready to use on this account.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowUploader(true)}
              className="rounded-full bg-white/75 px-4 py-2 text-xs font-medium text-slate-600 transition hover:bg-white hover:text-primary-600"
            >
              Use another resume
            </button>
          </div>
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`relative flex flex-col items-center justify-center rounded-[28px] border-2 border-dashed p-8 cursor-pointer transition-all ${
            isDragging
              ? 'border-primary-400 bg-primary-50'
              : 'border-white/50 bg-white/55 hover:border-primary-200 hover:bg-white/70'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
              }
            }}
          />

          {isUploading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-primary-600">Preparing your resume...</p>
                <p className="text-xs text-slate-500">This usually takes a moment.</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-primary-100 bg-primary-50 text-primary-500">
                <UploadCloud className="w-5 h-5" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-primary-600">
                  Drag and drop your resume, or <span className="text-primary-500 underline">browse</span>
                </p>
                <p className="mt-1 text-xs text-slate-500">Supports PDF and DOCX up to 10MB</p>
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
