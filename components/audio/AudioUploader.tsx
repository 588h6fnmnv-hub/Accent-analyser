'use client';

import { useState, useRef } from 'react';
import { Upload, FileAudio, Trash2, AlertCircle } from 'lucide-react';
import { DEFAULT_AUDIO_VALIDATION } from '@/types/audio';
import { AudioPlayer } from './AudioPlayer';

interface AudioUploaderProps {
  onFileSelected: (file: File) => void;
  onClear: () => void;
  selectedFile: File | null;
  audioPreviewUrl: string | null;
}

export function AudioUploader({
  onFileSelected,
  onClear,
  selectedFile,
  audioPreviewUrl,
}: AudioUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const validateAndSelectFile = (file: File) => {
    setError(null);

    // Validate size
    const maxSize = (DEFAULT_AUDIO_VALIDATION.maxSizeMB || 25) * 1024 * 1024;
    if (file.size > maxSize) {
      setError(`File size exceeds limit of ${DEFAULT_AUDIO_VALIDATION.maxSizeMB}MB.`);
      return;
    }

    if (file.size === 0) {
      setError('Selected audio file is empty.');
      return;
    }

    // Validate type / extension
    const allowedFormats = DEFAULT_AUDIO_VALIDATION.allowedFormats || [];
    const fileType = file.type.toLowerCase();
    const fileName = file.name.toLowerCase();

    const allowedExtensions = ['.wav', '.mp3', '.m4a', '.webm', '.ogg', '.aac', '.mp4', '.flac'];
    const hasValidExtension = allowedExtensions.some((ext) => fileName.endsWith(ext));
    const hasValidMime = allowedFormats.some((fmt) => fileType.includes(fmt.replace('audio/', '')));

    if (!hasValidExtension && !hasValidMime && fileType && !fileType.startsWith('audio/')) {
      setError('Invalid audio format. Please upload a valid MP3, WAV, M4A, or WebM audio file.');
      return;
    }

    onFileSelected(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelectFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelectFile(e.target.files[0]);
    }
  };

  const handleRemove = () => {
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClear();
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 bg-slate-900/60 border border-slate-800 rounded-2xl w-full max-w-xl mx-auto shadow-inner">
      {error && (
        <div className="w-full mb-4 p-3 bg-red-900/30 border border-red-700/50 rounded-xl flex items-center gap-3 text-red-200 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`w-full border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-colors ${
            isDragOver
              ? 'border-indigo-500 bg-indigo-950/20'
              : 'border-slate-700 hover:border-slate-500 bg-slate-950/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg,.aac"
            onChange={handleFileInput}
            className="hidden"
          />

          <div className="p-4 bg-slate-800/80 rounded-full text-indigo-400 mb-3">
            <Upload className="w-6 h-6" />
          </div>

          <p className="text-sm font-semibold text-white">Drag & drop your audio file here</p>
          <p className="text-xs text-slate-400 mt-1">or click to browse from your device</p>

          <p className="text-xs text-slate-500 mt-4">
            Supports MP3, WAV, M4A, WebM, OGG up to 25MB
          </p>
        </div>
      ) : (
        <div className="w-full space-y-4">
          <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
            <div className="flex items-center space-x-3 truncate mr-2">
              <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg">
                <FileAudio className="w-5 h-5" />
              </div>
              <div className="truncate">
                <p className="text-sm font-medium text-white truncate">{selectedFile.name}</p>
                <p className="text-xs text-slate-400">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </div>

            <button
              onClick={handleRemove}
              className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors"
              title="Remove File"
              aria-label="Remove File"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>

          {audioPreviewUrl && <AudioPlayer src={audioPreviewUrl} />}
        </div>
      )}
    </div>
  );
}
