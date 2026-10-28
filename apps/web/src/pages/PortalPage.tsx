import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, downloadPortalDocument, uploadPortalFile } from "../api";
import { Me } from "../session";

type PortalRequest = {
  document_request_id: string;
  title: string;
  due_on: string;
  status: string;
  document_id: string | null;
  blocks_close: boolean;
};

const STATUS: Record<string, string> = {
  open: "Pedido aberto",
  received: "Arquivo recebido",
};

export function PortalPage({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [fileById, setFileById] = useState<Record<string, File | null>>({});
  const requests = useQuery({
    queryKey: ["portal-requests", me.legal_entity_id],
    queryFn: () => api<{ items: PortalRequest[] }>("/v1/portal/document-requests"),
  });
  const send = useMutation({
    mutationFn: (requestId: string) => {
      const file = fileById[requestId];
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o arquivo deste pedido.");
      }
      return uploadPortalFile(requestId, file);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portal-requests", me.legal_entity_id] });
    },
  });
  const errorText = send.error instanceof ApiError ? send.error.message : send.error ? "Falha ao enviar o arquivo." : null;

  return (
    <main className="rastro">
      <section className="page-container">
        <section className="page-header">
          <div>
            <span className="eyebrow">{me.tenant_name}</span>
            <h1>{me.legal_entity_name ?? "Sua empresa"}</h1>
            <p>{me.legal_entity_cnpj ? `CNPJ ${me.legal_entity_cnpj}` : "Pedidos desta empresa."}</p>
          </div>
        </section>
        <section className="panel">
          <h2>Pedidos</h2>
          <p className="muted">Envie o arquivo pedido. Confirmar fica com o escritório. Esta tela não mostra lançamentos.</p>
          {requests.isLoading ? <p className="muted">Carregando pedidos.</p> : null}
          {requests.isError ? <p className="error">Não foi possível carregar os pedidos.</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
          {requests.data && requests.data.items.length === 0 ? <p className="muted">Nenhum pedido aberto.</p> : null}
          {requests.data && requests.data.items.length > 0 ? (
            <table>
              <thead>
                <tr><th>Pedido</th><th>Prazo</th><th>Estado</th><th></th></tr>
              </thead>
              <tbody>
                {requests.data.items.map((item) => (
                  <tr key={item.document_request_id}>
                    <td>{item.title}</td>
                    <td>{item.due_on.split("-").reverse().join("/")}</td>
                    <td>{STATUS[item.status] ?? item.status}{item.blocks_close ? " · bloqueia o fechamento" : ""}</td>
                    <td>
                      {item.status === "open" ? (
                        <form
                          className="row"
                          onSubmit={(event) => {
                            event.preventDefault();
                            send.mutate(item.document_request_id);
                          }}
                        >
                          <input
                            type="file"
                            aria-label={`Arquivo de ${item.title}`}
                            onChange={(event) =>
                              setFileById((current) => ({ ...current, [item.document_request_id]: event.target.files?.[0] ?? null }))
                            }
                          />
                          <button type="submit" disabled={!fileById[item.document_request_id] || send.isPending}>Enviar arquivo</button>
                        </form>
                      ) : null}
                      {item.document_id ? (
                        <button type="button" className="secondary" onClick={() => void downloadPortalDocument(item.document_id ?? "", `${item.title}.arquivo`)}>
                          Baixar arquivo
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      </section>
    </main>
  );
}
