import { jsonLdScriptPayload } from "@/lib/schema/jsonLd";

type JsonLdObject = Record<string, unknown>;

export function JsonLd(props: { data: JsonLdObject | JsonLdObject[] }) {
  const blocks = Array.isArray(props.data) ? props.data : [props.data];
  return (
    <>
      {blocks.map((obj, i) => (
        <script
          key={i}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScriptPayload(obj) }}
        />
      ))}
    </>
  );
}
