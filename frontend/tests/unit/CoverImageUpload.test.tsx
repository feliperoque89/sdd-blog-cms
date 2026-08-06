import { File as NodeFile } from "node:buffer";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";

// Contrato fixo: frontend/src/components/CoverImageUpload.tsx (SPEC-005)
import CoverImageUpload from "@/components/CoverImageUpload";

// `node:buffer`'s `File` (não o polyfill do jsdom): o `File` global do jsdom
// não é reconhecido pelo parser multipart do undici (usado por
// fetch/FormData no Node) — sem isso, qualquer teste que faz upload de
// verdade via MSW quebra com um erro interno de parsing, mesmo sem o
// handler chamar `request.formData()`.
function buildFile(name: string, type: string, content = "conteudo-fake") {
  return new NodeFile([content], name, { type }) as unknown as File;
}

describe("CoverImageUpload (SPEC-005)", () => {
  it("dado value nulo, então não mostra preview", () => {
    render(<CoverImageUpload value={null} onChange={vi.fn()} />);

    expect(screen.queryByAltText(/preview da imagem de capa/i)).not.toBeInTheDocument();
  });

  it("dado um value existente, então mostra o preview da imagem atual (RF05)", () => {
    render(
      <CoverImageUpload value="https://minio.local/media/cover-images/x.jpg" onChange={vi.fn()} />
    );

    expect(screen.getByAltText(/preview da imagem de capa/i)).toHaveAttribute(
      "src",
      "https://minio.local/media/cover-images/x.jpg"
    );
  });

  it("dado um arquivo selecionado, quando o upload termina, então chama onChange com a URL retornada", async () => {
    let requestReceived = false;
    server.use(
      http.post(`${API_URL}/api/admin/media/cover-image`, () => {
        requestReceived = true;
        return HttpResponse.json(
          { url: "https://minio.local/media/cover-images/novo.jpg" },
          { status: 201 }
        );
      })
    );

    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CoverImageUpload value={null} onChange={onChange} />);

    const file = buildFile("capa.jpg", "image/jpeg");
    const input = screen.getByLabelText(/imagem de capa/i);
    await user.upload(input, file);

    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith("https://minio.local/media/cover-images/novo.jpg")
    );
    expect(requestReceived).toBe(true);
  });

  it("dado um upload em andamento, então mostra o estado de carregamento", async () => {
    server.use(
      http.post(`${API_URL}/api/admin/media/cover-image`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return HttpResponse.json({ url: "https://minio.local/media/x.jpg" }, { status: 201 });
      })
    );

    const user = userEvent.setup();
    render(<CoverImageUpload value={null} onChange={vi.fn()} />);

    const file = buildFile("capa.jpg", "image/jpeg");
    await user.upload(screen.getByLabelText(/imagem de capa/i), file);

    expect(await screen.findByText(/enviando imagem/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/enviando imagem/i)).not.toBeInTheDocument());
  });

  it("dado um erro da API ao enviar, então mostra a mensagem via role=alert sem quebrar o componente", async () => {
    server.use(
      http.post(`${API_URL}/api/admin/media/cover-image`, () =>
        HttpResponse.json(
          { detail: "Tipo de arquivo não permitido. Envie uma imagem JPEG, PNG ou WebP." },
          { status: 422 }
        )
      )
    );

    const onChange = vi.fn();
    // `accept` no input é só uma dica de UI (RF02 valida de verdade por
    // assinatura de arquivo no backend) — `applyAccept: false` simula um
    // usuário que contorna o seletor nativo (ex.: renomeia a extensão),
    // que é exatamente o cenário que esse teste cobre.
    const user = userEvent.setup({ applyAccept: false });
    render(<CoverImageUpload value={null} onChange={onChange} />);

    const file = buildFile("capa.pdf", "application/pdf");
    await user.upload(screen.getByLabelText(/imagem de capa/i), file);

    expect(await screen.findByRole("alert")).toHaveTextContent(/tipo de arquivo não permitido/i);
    expect(onChange).not.toHaveBeenCalled();
    // O input continua utilizável para uma nova tentativa.
    expect(screen.getByLabelText(/imagem de capa/i)).not.toBeDisabled();
  });
});
