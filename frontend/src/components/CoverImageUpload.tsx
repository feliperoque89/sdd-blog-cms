"use client";

import { useState, type ChangeEvent } from "react";
import { uploadCoverImage } from "@/lib/media-client";

export interface CoverImageUploadProps {
  value: string | null;
  onChange: (url: string) => void;
}

const ACCEPTED_TYPES = "image/jpeg,image/png,image/webp";

/**
 * Upload da imagem de capa do post (SPEC-005 / RF05), substituindo o campo
 * de texto livre de `cover_image_url`. Mostra um preview de `value` (se
 * houver) e, ao selecionar um arquivo, envia via
 * `POST /api/admin/media/cover-image` e propaga a URL retornada via
 * `onChange` — validação de tipo/tamanho é sempre responsabilidade do
 * backend (RF02/RF03).
 */
export default function CoverImageUpload({ value, onChange }: CoverImageUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Permite selecionar o mesmo arquivo de novo depois de um erro.
    event.target.value = "";
    if (!file) {
      return;
    }

    setError(null);
    setIsUploading(true);

    try {
      const result = await uploadCoverImage(file);
      onChange(result.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível enviar a imagem.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {value && (
        // eslint-disable-next-line @next/next/no-img-element -- URL vem do MinIO/S3 (host dinâmico por ambiente), não do domínio de imagens otimizadas do Next.
        <img
          src={value}
          alt="Preview da imagem de capa"
          className="h-40 w-full rounded border border-gray-300 object-cover"
        />
      )}

      <label htmlFor="post-cover-image-upload" className="text-sm font-medium text-foreground">
        Imagem de capa
      </label>
      <input
        id="post-cover-image-upload"
        name="cover_image_upload"
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={(event) => void handleFileChange(event)}
        disabled={isUploading}
        className="text-sm"
      />

      {isUploading && <p className="text-sm text-gray-600">Enviando imagem...</p>}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
