import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, downloadDocument, uploadDocument, api } from "../api";
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

export function DocumentsPage() {
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const [documentType, setDocumentType] = useState("other");
  const [filter, setFilter] = useState("");
  const [competence, setCompetence] = useState("");
  const [file, setFile] = useState<File | null>(null);
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
      <p className="muted">O arquivo original fica no armazenamento com o hash. Esta tela não guarda senha, certificado nem o conteúdo em log.</p>
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
