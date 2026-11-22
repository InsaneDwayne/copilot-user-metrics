// Regenerates theme.schema.json (editor autocomplete for theme.json) from the zod schema,
// next to the default theme, which the image serves (and operators copy as a starting point).
import { writeFileSync } from 'node:fs'
import { z } from 'zod'
import { themeConfigSchema } from '../src/config/themeSchema.ts'

type JsonSchema = { [key: string]: unknown }

// zod writes a record with enum keys (the token overrides) as `propertyNames: { enum }`.
// Editors validate that but only autocomplete keys listed under `properties`, so list them.
function listEnumKeys(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(listEnumKeys)
  if (!node || typeof node !== 'object') return node
  const schema = Object.fromEntries(Object.entries(node).map(([k, v]) => [k, listEnumKeys(v)])) as JsonSchema
  const keys = (schema.propertyNames as JsonSchema | undefined)?.enum
  if (Array.isArray(keys) && schema.additionalProperties) {
    const { propertyNames: _, additionalProperties: value, ...rest } = schema
    return { ...rest, properties: Object.fromEntries(keys.map((key) => [key, value])), additionalProperties: false }
  }
  return schema
}

const schema = listEnumKeys(
  z.toJSONSchema(themeConfigSchema.extend({ $schema: z.string().optional() }), { io: 'input' }),
)
const target = '../public/theme/theme.schema.json'
writeFileSync(new URL(target, import.meta.url), `${JSON.stringify(schema, null, 2)}\n`)
console.log(`wrote ${target.replace(/^\.\.\//, '')}`)
