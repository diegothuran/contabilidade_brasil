import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api, downloadDocument, uploadDocument } from "../api";
import { can, useSession } from "../session";

type DocumentItem = {
  document_id: string;
  document_type: string;
  competence: string | null;
  original: { file_name: string; sha256: string; size_bytes: number };
};

const TYPES = [
  ["other", "Outro"],
  ["invoice", "Nota"],
  ["bank_statement", "Extrato"],
  ["receipt", "Recibo"],
  ["contract", "Contrato"],
  ["tax_file", "Arquivo fiscal"],
  ["journal_support", "Suporte de lançamento"],
  ["government_response", "Retorno de órgão"],
] as const;

const EXPORT_STATUS: Record<string, string> = {
  accepted: "Em fila",
  running: "Gerando",
  completed: "Pronto",
  failed: "Falhou",
};

export function DocumentsPage() {
  const { entityId, periodId, me } = useSession();
  const queryClient = useQueryClient();
  const [documentType, setDocumentType] = useState("other");
  const [filter, setFilter] = useState("");
  const [competence, setCompetence] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [exportId, setExportId] = useState<string | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  const documents = useQuery({
    queryKey: ["documents", entityId, filter],
    queryFn: () => {
      const params = new URLSearchParams({ legal_entity_id: entityId });
      if (filter) {
        params.set("document_type", filter);
      }
      return api<{ items: DocumentItem[] }>(`/v1/documents?${params.toString()}`);
    },
  });
  const operation = useQuery({
    queryKey: ["operation", operationId],
    enabled: Boolean(operationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "accepted" || status === "running" ? 2000 : false;
    },
    queryFn: () => api<{ status: string; error_code: string | null; correlation_id: string }>(`/v1/operations/${operationId}`),
  });
  const startExport = useMutation({
    mutationFn: () =>
      api<{ export_id: string; operation_id: string; status: string }>("/v1/legal-entities/" + entityId + "/exports", {
        body: { period_id: periodId, kind: "operational_v1" },
      }),
    onSuccess: (created) => {
      setExportId(created.export_id);
      setOperationId(created.operation_id);
    },
  });
  const canExport = can(me.roles, "preparer", "approver", "admin");
  const upload = useMutation({
    mutationFn: () => {
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha um arquivo.");
      }
      return uploadDocument(file, {
        document_type: documentType,
        legal_entity_id: entityId,
        competence,
      });
    },
    onSuccess: async () => {
      setFile(null);
      await queryClient.invalidateQueries({ queryKey: ["documents", entityId] });
    },
  });

  return (
    <section>
      <h1>Evidências</h1>
      <p className="muted">O arquivo original fica no armazenamento com o hash. Esta tela não guarda senha, certificado nem o conteúdo em log. A exportação da competência não lista as operações do escritório: ela acompanha só este pedido.</p>
      <section className="panel">
        <h2>Exportação da competência</h2>
        {!periodId ? <p className="muted">Escolha a competência na barra.</p> : null}
        {canExport ? (
          <button type="button" disabled={!periodId || startExport.isPending} onClick={() => startExport.mutate()}>
            Gerar exportação
          </button>
        ) : (
          <p className="muted">A consulta não dispara outra exportação.</p>
        )}
        {operation.data ? <p>Estado: {EXPORT_STATUS[operation.data.status] ?? operation.data.status}</p> : null}
        {operation.data?.status === "failed" ? <p className="error">A exportação falhou.</p> : null}
        {operation.data?.status === "completed" && exportId ? (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              void api<Record<string, unknown>>(`/v1/exports/${exportId}`).then((payload) => {
                const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = `exportacao-${exportId}.json`;
                anchor.click();
                URL.revokeObjectURL(url);
              });
            }}
          >
            Baixar JSON
          </button>
        ) : null}
        {startExport.isError ? (
          <p className="error">{startExport.error instanceof ApiError ? startExport.error.message : "Falha ao pedir a exportação."}</p>
        ) : null}
      </section>
      {can(me.roles, "preparer", "approver", "admin") ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            upload.mutate();
          }}
        >
          <label>
            Tipo
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              {TYPES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Competência
            <input value={competence} placeholder="AAAA-MM" onChange={(event) => setCompetence(event.target.value)} />
          </label>
          <label>
            Arquivo
            <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" disabled={!file || upload.isPending}>Enviar</button>
        </form>
      ) : null}
      {upload.isError ? <p className="error">{upload.error instanceof ApiError ? `${upload.error.title}. ${upload.error.message}` : "Falha no envio."}</p> : null}
      <label>
        Filtrar por tipo
        <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="">Todos</option>
          {TYPES.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <table>
        <thead>
          <tr><th>Arquivo</th><th>Tipo</th><th>Competência</th><th>Hash</th><th></th></tr>
        </thead>
        <tbody>
          {(documents.data?.items ?? []).map((item) => (
            <tr key={item.document_id}>
              <td>{item.original.file_name}</td>
              <td>{TYPES.find(([value]) => value === item.document_type)?.[1] ?? item.document_type}</td>
              <td>{item.competence ?? "—"}</td>
              <td className="muted">{item.original.sha256.slice(0, 12)}</td>
              <td>
                <button type="button" className="secondary" onClick={() => void downloadDocument(item.document_id, item.original.file_name)}>
                  Baixar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
