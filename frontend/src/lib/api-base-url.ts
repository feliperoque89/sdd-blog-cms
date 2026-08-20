/**
 * URL base do backend, resolvida de forma diferente conforme onde o código
 * roda — o Ingress (k8s/09-ingress.yaml) serve frontend e backend no MESMO
 * host, mas Server Components (SSR) executam dentro do próprio pod:
 *
 * - Servidor: `API_URL`, lida em runtime (não é `NEXT_PUBLIC_*`, então não
 *   fica embutida no build) — DNS interno do cluster (`http://backend:8000`).
 *   Nunca usar o IP externo do Ingress aqui: o pod tentando voltar pro IP
 *   público do próprio Load Balancer é hairpin NAT, que o GKE não garante.
 * - Navegador: `NEXT_PUBLIC_API_URL`, embutida no bundle em build-time.
 *   Vazia/ausente = mesma origem (`/api/...` relativo), o caso normal em
 *   produção já que o Ingress serve os dois no mesmo IP. Só precisa de
 *   valor absoluto em dev local, onde front e back rodam em portas
 *   diferentes (ver frontend/.env.example).
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }

  return process.env.NEXT_PUBLIC_API_URL ?? "";
}
