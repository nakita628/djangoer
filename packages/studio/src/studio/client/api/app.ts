type DeepReadonly<T> = T extends (infer R)[]
  ? readonly DeepReadonly<R>[]
  : T extends object
    ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
    : T
type SchemaFile = { path: string; content: string }
type FieldRelation = {
  name: string | null
  fromFields: string[]
  toFields: string[]
  onDelete: string | null
  onUpdate: string | null
  through: string | null
}
type Field = {
  name: string
  dbName: string | null
  kind: 'scalar' | 'object' | 'enum' | 'unsupported'
  type: string
  isList: boolean
  isRequired: boolean
  isId: boolean
  isUnique: boolean
  isUpdatedAt: boolean
  isForeignKey: boolean
  default: string | null
  dbDefault: string | null
  generated: string | null
  nativeType: string | null
  stored: boolean | null
  collation: string | null
  maxDigits: number | null
  decimalPlaces: number | null
  documentation: string | null
  annotations: string[]
  relation: FieldRelation | null
  attributes: string[]
}
type Index = {
  type: 'id' | 'unique' | 'normal' | 'fulltext' | 'exclusion'
  name: string | null
  dbName: string | null
  fields: string[]
  expressions: string[]
  condition: string | null
  opclasses: string[]
  method: string | null
  include: string[]
  parameters: string[]
  descending: string[]
  deferrable: string | null
  nullsDistinct: boolean | null
  attribute: string
}
type GenericForeignKey = { name: string; contentTypeField: string; objectIdField: string }
type Check = { name: string; expression: string }
type ProxyModel = { name: string; app: string; documentation: string | null }
type AbstractBase = { name: string; fields: string[] }
type Location = { file: string; line: number }
type Model = {
  name: string
  app: string
  dbName: string | null
  documentation: string | null
  annotations: string[]
  fields: Field[]
  primaryKey: string[] | null
  indexes: Index[]
  genericForeignKeys: GenericForeignKey[]
  checks: Check[]
  proxies: ProxyModel[]
  abstractBases: AbstractBase[]
  managed: boolean
  attributes: string[]
  location: Location | null
  own: boolean
}
type EnumValue = { name: string; dbName: string | null; group: string | null }
type Enum = {
  name: string
  dbName: string | null
  documentation: string | null
  values: EnumValue[]
  location: Location | null
}
type RelationEnd = {
  model: string
  field: string
  cardinality: 'zero-one' | 'one' | 'zero-many' | 'many'
}
type Through = {
  dbName: string
  fromColumn: string
  toColumn: string
  fields: Field[]
  indexes: Index[]
}
type Relation = {
  id: string
  name: string | null
  origin: 'inferred' | 'annotated' | 'implicit-many-to-many' | 'generic'
  from: RelationEnd
  to: RelationEnd
  onDelete: string | null
  onUpdate: string | null
  through: Through | null
  constrained: boolean
  parentLink: boolean
}
type Schema = {
  files: SchemaFile[]
  provider: string | null
  models: Model[]
  enums: Enum[]
  relations: Relation[]
}
type LspPosition = { line: number; character: number }
type LspRange = { start: LspPosition; end: LspPosition }
type FileDiagnostic = {
  path: string
  range: LspRange
  message: string
  severity: 'error' | 'warning' | 'information' | 'hint'
}
type Snapshot = {
  schema: Schema | null
  error: string | null
  diagnostics: FileDiagnostic[]
  updatedAt: string | string
  files: SchemaFile[]
}
type FileWrite = { path: string; content: string }
type NotFoundProblem = {
  detail: string
  instance: string
  type?: '/problems/not-found' | undefined
  title?: 'Not Found' | undefined
  status?: 404 | undefined
}
type FieldError = { field: string; message: string }
type ValidationProblem = {
  detail: string
  instance: string
  type?: '/problems/validation-failed' | undefined
  title?: 'Validation Failed' | undefined
  status?: 422 | undefined
  errors: FieldError[]
}
type SourcePositionBody = { path: string; content: string; offset: number }
type ClientCompletionItem = {
  label: string
  kind: string
  sortText: string
  insertText: string | null
}
type ClientCompletions = { items: ClientCompletionItem[] }
type TextRange = { start: number; end: number }
type ClientHover = { contents: string | null; range: TextRange | null }
type SourceBody = { path: string; content: string }
type ClientTypeDiagnostic = {
  message: string
  severity: 'error' | 'warning' | 'info'
  range: TextRange
}
type ClientTypeDiagnostics = { diagnostics: ClientTypeDiagnostic[] }
type DbStatus = {
  connected: boolean
  dialect: 'postgresql' | 'mysql' | 'sqlite' | null
  url: string | null
  source: 'settings' | null
  error: string | null
}
type Counts = { counts: { [x: string]: number } }
type ServiceUnavailableProblem = {
  detail: string
  instance: string
  type?: '/problems/service-unavailable' | undefined
  title?: 'Service Unavailable' | undefined
  status?: 503 | undefined
}
type Rows = {
  rows: { [x: string]: string | number | number | boolean | null }[]
  total: number
  skip: number
  take: number
  key: string[]
  columns: string[]
}
type InsertBody = { values: { [x: string]: string | number | number | boolean | null } }
type Affected = { affected: number }
type UpdateBody = {
  where: { [x: string]: string | number | number | boolean | null }
  values: { [x: string]: string | number | number | boolean | null }
}
type DeleteBody = { where: { [x: string]: string | number | number | boolean | null } }
type SqlBody = { sql: string; params?: (string | number | number | boolean | null)[] | undefined }
type SqlResult = {
  columns: string[]
  rows: { [x: string]: string | number | number | boolean | null }[]
  rowCount: number
  durationMs: number
}
type PlanNode = {
  id: string
  parent: string | null
  label: string
  detail: string | null
  cost: number | null
  rows: number | null
}
type Plan = { dialect: 'postgresql' | 'mysql' | 'sqlite'; nodes: PlanNode[]; raw: string }
type AnalyzeBody = { sql: string }
type NodeColumn = { name: string; dataType: string | null; used: boolean }
type GraphNode = {
  id: string
  kind:
    | 'table'
    | 'cte'
    | 'subquery'
    | 'values'
    | 'function'
    | 'join'
    | 'filter'
    | 'aggregate'
    | 'having'
    | 'project'
    | 'distinct'
    | 'sort'
    | 'limit'
    | 'union'
    | 'insert'
    | 'update'
    | 'delete'
    | 'returning'
  label: string
  details: string[]
  range: TextRange | null
  scope: string
  columns: NodeColumn[]
}
type GraphEdge = {
  id: string
  source: string
  target: string
  label: string | null
  kind: 'flow' | 'lookup'
}
type TableRef = {
  nodeId: string
  name: string
  alias: string | null
  scope: string
  known: boolean
  columnsUsed: string[]
  range: TextRange
}
type ColumnSource = { table: string; column: string }
type OutputColumn = {
  name: string
  expression: string
  dataType: string | null
  tsType: string
  nullable: boolean | null
  sources: ColumnSource[]
}
type SqlParameter = {
  index: number
  placeholder: string
  dataType: string | null
  tsType: string
  nullable: boolean | null
  context: string
}
type SqlDiagnostic = {
  severity: 'error' | 'warning' | 'info'
  message: string
  range: TextRange | null
}
type StatementAnalysis = {
  kind: 'select' | 'insert' | 'update' | 'delete' | 'other' | 'invalid'
  text: string
  range: TextRange
  nodes: GraphNode[]
  edges: GraphEdge[]
  tables: TableRef[]
  columns: OutputColumn[]
  parameters: SqlParameter[]
  diagnostics: SqlDiagnostic[]
  rowType: string
  paramsType: string
}
type Analysis = { statements: StatementAnalysis[] }
type ClientStatus = {
  available: boolean
  source: string | null
  error: string | null
  typescript: string | null
  typesError: string | null
}
type ClientQueryBody = { query: string }
type ClientCall = { model: string; operation: string; write: boolean; range: TextRange }
type ClientTouchedModel = { model: string; fields: string[] }
type ClientDiagnostic = { message: string; range: TextRange }
type ClientAnalysis = {
  calls: ClientCall[]
  transaction: boolean
  touched: ClientTouchedModel[]
  diagnostics: ClientDiagnostic[]
}
type ClientPositionBody = { query: string; offset: number }
type ClientCompletionDetailBody = { query: string; offset: number; name: string }
type ClientCompletionDetail = { detail: string | null; documentation: string | null }
type ClientSignatureParameter = { label: string; documentation: string | null }
type ClientSignature = {
  label: string
  documentation: string | null
  parameters: ClientSignatureParameter[]
}
type ClientSignatureHelp = {
  signatures: ClientSignature[]
  activeSignature: number
  activeParameter: number
}
type ClientFormatted = { text: string }
type ClientRunBody = { query: string }
type ClientSqlQuery = {
  sql: string
  formatted: string
  params: (string | number | number | boolean | null)[]
  durationMs: number
}
type ClientPreview = { queries: ClientSqlQuery[]; durationMs: number }
type ClientResult = {
  result: { [x: string]: unknown }
  rowCount: number | null
  truncated: boolean
  queries: ClientSqlQuery[]
  durationMs: number
}
type DocsDirective = { name: string; values: string[] }
type DocsField = {
  name: string
  type: string
  bareTypeName: string
  kind: 'scalar' | 'object' | 'enum' | 'unsupported'
  directives: string[]
  documentation: string | null
  required: boolean
}
type DocsTypeRef = {
  type: string
  isList: boolean
  location: 'scalar' | 'inputObjectTypes' | 'outputObjectTypes' | 'enumTypes' | 'fieldRefTypes'
}
type DocsOperationInput = { name: string; types: DocsTypeRef[]; required: boolean }
type DocsOperationOutput = { type: string | null; required: boolean; list: boolean }
type DocsOperation = {
  name: string
  description: string
  usage: string
  inputs: DocsOperationInput[] | null
  output: DocsOperationOutput
}
type DocsModel = {
  name: string
  documentation: string | null
  directives: DocsDirective[]
  fields: DocsField[]
  operations: DocsOperation[]
}
type DocsTypeField = { name: string; types: DocsTypeRef[]; nullable: boolean }
type DocsObjectType = { name: string; fields: DocsTypeField[] }
type DocsEnum = { name: string; values: string[] }
type Docs = {
  models: DocsModel[]
  inputTypes: DocsObjectType[]
  outputTypes: DocsObjectType[]
  enumTypes: DocsEnum[]
}
declare const routes: import('@hono/zod-openapi').OpenAPIHono<
  import('hono/types').Env,
  DeepReadonly<
    {
      '/api/schema': { $get: { input: {}; output: Snapshot; outputFormat: 'json'; status: 200 } }
    } & {
      '/api/schema/reload': {
        $post: { input: {}; output: Snapshot; outputFormat: 'json'; status: 200 }
      }
    } & {
      '/api/schema/files': {
        $put:
          | { input: { json: FileWrite }; output: SchemaFile; outputFormat: 'json'; status: 200 }
          | {
              input: { json: FileWrite }
              output: NotFoundProblem
              outputFormat: 'json'
              status: 404
            }
          | {
              input: { json: FileWrite }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/schema/complete': {
        $post:
          | {
              input: { json: SourcePositionBody }
              output: ClientCompletions
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: SourcePositionBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/schema/hover': {
        $post:
          | {
              input: { json: SourcePositionBody }
              output: ClientHover
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: SourcePositionBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/schema/check': {
        $post:
          | {
              input: { json: SourceBody }
              output: ClientTypeDiagnostics
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: SourceBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/schema/preview': {
        $post:
          | { input: { json: SourceBody }; output: Schema; outputFormat: 'json'; status: 200 }
          | {
              input: { json: SourceBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/db': { $get: { input: {}; output: DbStatus; outputFormat: 'json'; status: 200 } }
    } & {
      '/api/db/counts': {
        $get:
          | { input: {}; output: Counts; outputFormat: 'json'; status: 200 }
          | { input: {}; output: ServiceUnavailableProblem; outputFormat: 'json'; status: 503 }
      }
    } & {
      '/api/db/rows/:modelName': {
        $get:
          | {
              input: { param: { modelName: string } } & {
                query: {
                  skip?: number | undefined
                  take?: number | undefined
                  search?: string | null | undefined
                }
              }
              output: Rows
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { param: { modelName: string } } & {
                query: {
                  skip?: number | undefined
                  take?: number | undefined
                  search?: string | null | undefined
                }
              }
              output: NotFoundProblem
              outputFormat: 'json'
              status: 404
            }
          | {
              input: { param: { modelName: string } } & {
                query: {
                  skip?: number | undefined
                  take?: number | undefined
                  search?: string | null | undefined
                }
              }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { param: { modelName: string } } & {
                query: {
                  skip?: number | undefined
                  take?: number | undefined
                  search?: string | null | undefined
                }
              }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
        $post:
          | {
              input: { param: { modelName: string } } & { json: InsertBody }
              output: Affected
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { param: { modelName: string } } & { json: InsertBody }
              output: NotFoundProblem
              outputFormat: 'json'
              status: 404
            }
          | {
              input: { param: { modelName: string } } & { json: InsertBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { param: { modelName: string } } & { json: InsertBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
        $patch:
          | {
              input: { param: { modelName: string } } & { json: UpdateBody }
              output: Affected
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { param: { modelName: string } } & { json: UpdateBody }
              output: NotFoundProblem
              outputFormat: 'json'
              status: 404
            }
          | {
              input: { param: { modelName: string } } & { json: UpdateBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { param: { modelName: string } } & { json: UpdateBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
        $delete:
          | {
              input: { param: { modelName: string } } & { json: DeleteBody }
              output: Affected
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { param: { modelName: string } } & { json: DeleteBody }
              output: NotFoundProblem
              outputFormat: 'json'
              status: 404
            }
          | {
              input: { param: { modelName: string } } & { json: DeleteBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { param: { modelName: string } } & { json: DeleteBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
      }
    } & {
      '/api/db/sql': {
        $post:
          | { input: { json: SqlBody }; output: SqlResult; outputFormat: 'json'; status: 200 }
          | {
              input: { json: SqlBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { json: SqlBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
      }
    } & {
      '/api/db/explain': {
        $post:
          | { input: { json: SqlBody }; output: Plan; outputFormat: 'json'; status: 200 }
          | {
              input: { json: SqlBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { json: SqlBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
      }
    } & {
      '/api/db/analyze': {
        $post:
          | { input: { json: AnalyzeBody }; output: Analysis; outputFormat: 'json'; status: 200 }
          | {
              input: { json: AnalyzeBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client': {
        $get: { input: {}; output: ClientStatus; outputFormat: 'json'; status: 200 }
      }
    } & {
      '/api/client/analyze': {
        $post:
          | {
              input: { json: ClientQueryBody }
              output: ClientAnalysis
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientQueryBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/check': {
        $post:
          | {
              input: { json: ClientQueryBody }
              output: ClientTypeDiagnostics
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientQueryBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/complete': {
        $post:
          | {
              input: { json: ClientPositionBody }
              output: ClientCompletions
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientPositionBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/complete/detail': {
        $post:
          | {
              input: { json: ClientCompletionDetailBody }
              output: ClientCompletionDetail
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientCompletionDetailBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/hover': {
        $post:
          | {
              input: { json: ClientPositionBody }
              output: ClientHover
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientPositionBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/signature': {
        $post:
          | {
              input: { json: ClientPositionBody }
              output: ClientSignatureHelp
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientPositionBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/format': {
        $post:
          | {
              input: { json: ClientQueryBody }
              output: ClientFormatted
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientQueryBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
      }
    } & {
      '/api/client/preview': {
        $post:
          | {
              input: { json: ClientRunBody }
              output: ClientPreview
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientRunBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { json: ClientRunBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
      }
    } & {
      '/api/client/run': {
        $post:
          | {
              input: { json: ClientRunBody }
              output: ClientResult
              outputFormat: 'json'
              status: 200
            }
          | {
              input: { json: ClientRunBody }
              output: ValidationProblem
              outputFormat: 'json'
              status: 422
            }
          | {
              input: { json: ClientRunBody }
              output: ServiceUnavailableProblem
              outputFormat: 'json'
              status: 503
            }
      }
    } & { '/api/docs': { $get: { input: {}; output: Docs; outputFormat: 'json'; status: 200 } } }
  >,
  '/'
>
export default routes
