import {
  useQuery,
  useSuspenseQuery,
  useMutation,
  queryOptions,
  mutationOptions,
} from '@tanstack/react-query'
import type {
  UseQueryOptions,
  UseSuspenseQueryOptions,
  UseMutationOptions,
  DefaultError,
  QueryClient,
} from '@tanstack/react-query'
import type { ClientRequestOptions, InferRequestType } from 'hono/client'
import { parseResponse } from 'hono/client'
import { client } from '../api'

export function getClientKey() {
  return ['client'] as const
}

export function getDbKey() {
  return ['db'] as const
}

export function getDocsKey() {
  return ['docs'] as const
}

export function getSchemaKey() {
  return ['schema'] as const
}

export function getSchemaQueryKey() {
  return ['schema', '/schema'] as const
}

export function getSchemaQueryOptions<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
  TError = DefaultError,
>(options?: ClientRequestOptions) {
  return queryOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
    TError,
    TData,
    ReturnType<typeof getSchemaQueryKey>
  >({
    queryKey: getSchemaQueryKey(),
    queryFn({ signal }) {
      return parseResponse(
        client.schema.$get(undefined, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useSchema<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getSchemaQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getSchemaQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseSchema<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getSchemaQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getSchemaQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function getPostSchemaReloadMutationKey() {
  return ['schema', '/schema/reload', 'POST'] as const
}

export function getPostSchemaReloadMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.reload.$post>>>>
    >,
    TError,
    void,
    TOnMutateResult
  >({
    mutationKey: getPostSchemaReloadMutationKey(),
    async mutationFn() {
      return parseResponse(client.schema.reload.$post(undefined, options))
    },
  })
}

export function usePostSchemaReload<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.schema.reload.$post>>>>
        >,
        TError,
        void,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostSchemaReloadMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getDbQueryKey() {
  return ['db', '/db'] as const
}

export function getDbQueryOptions<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
  TError = DefaultError,
>(options?: ClientRequestOptions) {
  return queryOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
    TError,
    TData,
    ReturnType<typeof getDbQueryKey>
  >({
    queryKey: getDbQueryKey(),
    queryFn({ signal }) {
      return parseResponse(
        client.db.$get(undefined, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useDb<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getDbQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getDbQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseDb<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getDbQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getDbQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function getDbCountsQueryKey() {
  return ['db', '/db/counts'] as const
}

export function getDbCountsQueryOptions<
  TData = Awaited<
    ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>
  >,
  TError = DefaultError,
>(options?: ClientRequestOptions) {
  return queryOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>>,
    TError,
    TData,
    ReturnType<typeof getDbCountsQueryKey>
  >({
    queryKey: getDbCountsQueryKey(),
    queryFn({ signal }) {
      return parseResponse(
        client.db.counts.$get(undefined, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useDbCounts<
  TData = Awaited<
    ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>
  >,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>
        >,
        TError,
        TData,
        ReturnType<typeof getDbCountsQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getDbCountsQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseDbCounts<
  TData = Awaited<
    ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>
  >,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.counts.$get>>>>
        >,
        TError,
        TData,
        ReturnType<typeof getDbCountsQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getDbCountsQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function getDbRowsModelNameQueryKey(
  args: InferRequestType<(typeof client.db.rows)[':modelName']['$get']>,
) {
  return ['db', '/db/rows/:modelName', args] as const
}

export function getDbRowsModelNameQueryOptions<
  TData = Awaited<
    ReturnType<
      typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
    >
  >,
  TError = DefaultError,
>(
  args: InferRequestType<(typeof client.db.rows)[':modelName']['$get']>,
  options?: ClientRequestOptions,
) {
  return queryOptions<
    Awaited<
      ReturnType<
        typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
      >
    >,
    TError,
    TData,
    ReturnType<typeof getDbRowsModelNameQueryKey>
  >({
    queryKey: getDbRowsModelNameQueryKey(args),
    queryFn({ signal }) {
      return parseResponse(
        client.db.rows[':modelName'].$get(args, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useDbRowsModelName<
  TData = Awaited<
    ReturnType<
      typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
    >
  >,
  TError = DefaultError,
>(
  args: InferRequestType<(typeof client.db.rows)[':modelName']['$get']>,
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
          >
        >,
        TError,
        TData,
        ReturnType<typeof getDbRowsModelNameQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getDbRowsModelNameQueryOptions<TData, TError>(args, clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseDbRowsModelName<
  TData = Awaited<
    ReturnType<
      typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
    >
  >,
  TError = DefaultError,
>(
  args: InferRequestType<(typeof client.db.rows)[':modelName']['$get']>,
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$get']>>>
          >
        >,
        TError,
        TData,
        ReturnType<typeof getDbRowsModelNameQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getDbRowsModelNameQueryOptions<TData, TError>(args, clientOptions), ...queryOptions },
    queryClient,
  )
}

export function getPostDbRowsModelNameMutationKey() {
  return ['db', '/db/rows/:modelName', 'POST'] as const
}

export function getPostDbRowsModelNameMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<
        typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$post']>>>
      >
    >,
    TError,
    InferRequestType<(typeof client.db.rows)[':modelName']['$post']>,
    TOnMutateResult
  >({
    mutationKey: getPostDbRowsModelNameMutationKey(),
    async mutationFn(args: InferRequestType<(typeof client.db.rows)[':modelName']['$post']>) {
      return parseResponse(client.db.rows[':modelName'].$post(args, options))
    },
  })
}

export function usePostDbRowsModelName<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<
              Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$post']>>
            >
          >
        >,
        TError,
        InferRequestType<(typeof client.db.rows)[':modelName']['$post']>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostDbRowsModelNameMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getDeleteDbRowsModelNameMutationKey() {
  return ['db', '/db/rows/:modelName', 'DELETE'] as const
}

export function getDeleteDbRowsModelNameMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<
        typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$delete']>>>
      >
    >,
    TError,
    InferRequestType<(typeof client.db.rows)[':modelName']['$delete']>,
    TOnMutateResult
  >({
    mutationKey: getDeleteDbRowsModelNameMutationKey(),
    async mutationFn(args: InferRequestType<(typeof client.db.rows)[':modelName']['$delete']>) {
      return parseResponse(client.db.rows[':modelName'].$delete(args, options))
    },
  })
}

export function useDeleteDbRowsModelName<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<
              Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$delete']>>
            >
          >
        >,
        TError,
        InferRequestType<(typeof client.db.rows)[':modelName']['$delete']>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getDeleteDbRowsModelNameMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPatchDbRowsModelNameMutationKey() {
  return ['db', '/db/rows/:modelName', 'PATCH'] as const
}

export function getPatchDbRowsModelNameMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<
        typeof parseResponse<Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$patch']>>>
      >
    >,
    TError,
    InferRequestType<(typeof client.db.rows)[':modelName']['$patch']>,
    TOnMutateResult
  >({
    mutationKey: getPatchDbRowsModelNameMutationKey(),
    async mutationFn(args: InferRequestType<(typeof client.db.rows)[':modelName']['$patch']>) {
      return parseResponse(client.db.rows[':modelName'].$patch(args, options))
    },
  })
}

export function usePatchDbRowsModelName<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<
              Awaited<ReturnType<(typeof client.db.rows)[':modelName']['$patch']>>
            >
          >
        >,
        TError,
        InferRequestType<(typeof client.db.rows)[':modelName']['$patch']>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPatchDbRowsModelNameMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostDbSqlMutationKey() {
  return ['db', '/db/sql', 'POST'] as const
}

export function getPostDbSqlMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.sql.$post>>>>>,
    TError,
    InferRequestType<typeof client.db.sql.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostDbSqlMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.db.sql.$post>) {
      return parseResponse(client.db.sql.$post(args, options))
    },
  })
}

export function usePostDbSql<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.sql.$post>>>>>,
        TError,
        InferRequestType<typeof client.db.sql.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostDbSqlMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostDbExplainMutationKey() {
  return ['db', '/db/explain', 'POST'] as const
}

export function getPostDbExplainMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.explain.$post>>>>>,
    TError,
    InferRequestType<typeof client.db.explain.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostDbExplainMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.db.explain.$post>) {
      return parseResponse(client.db.explain.$post(args, options))
    },
  })
}

export function usePostDbExplain<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.explain.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.db.explain.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostDbExplainMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostDbAnalyzeMutationKey() {
  return ['db', '/db/analyze', 'POST'] as const
}

export function getPostDbAnalyzeMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.analyze.$post>>>>>,
    TError,
    InferRequestType<typeof client.db.analyze.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostDbAnalyzeMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.db.analyze.$post>) {
      return parseResponse(client.db.analyze.$post(args, options))
    },
  })
}

export function usePostDbAnalyze<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.db.analyze.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.db.analyze.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostDbAnalyzeMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getClientQueryKey() {
  return ['client', '/client'] as const
}

export function getClientQueryOptions<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
  TError = DefaultError,
>(options?: ClientRequestOptions) {
  return queryOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
    TError,
    TData,
    ReturnType<typeof getClientQueryKey>
  >({
    queryKey: getClientQueryKey(),
    queryFn({ signal }) {
      return parseResponse(
        client.client.$get(undefined, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useClient<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getClientQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getClientQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseClient<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getClientQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getClientQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function getPostClientAnalyzeMutationKey() {
  return ['client', '/client/analyze', 'POST'] as const
}

export function getPostClientAnalyzeMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.analyze.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.analyze.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientAnalyzeMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.analyze.$post>) {
      return parseResponse(client.client.analyze.$post(args, options))
    },
  })
}

export function usePostClientAnalyze<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.analyze.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.analyze.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientAnalyzeMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientCheckMutationKey() {
  return ['client', '/client/check', 'POST'] as const
}

export function getPostClientCheckMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.check.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.check.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientCheckMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.check.$post>) {
      return parseResponse(client.client.check.$post(args, options))
    },
  })
}

export function usePostClientCheck<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.check.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.check.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientCheckMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientCompleteMutationKey() {
  return ['client', '/client/complete', 'POST'] as const
}

export function getPostClientCompleteMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.complete.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.complete.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientCompleteMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.complete.$post>) {
      return parseResponse(client.client.complete.$post(args, options))
    },
  })
}

export function usePostClientComplete<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.complete.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.complete.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientCompleteMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientCompleteDetailMutationKey() {
  return ['client', '/client/complete/detail', 'POST'] as const
}

export function getPostClientCompleteDetailMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<
        typeof parseResponse<Awaited<ReturnType<typeof client.client.complete.detail.$post>>>
      >
    >,
    TError,
    InferRequestType<typeof client.client.complete.detail.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientCompleteDetailMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.complete.detail.$post>) {
      return parseResponse(client.client.complete.detail.$post(args, options))
    },
  })
}

export function usePostClientCompleteDetail<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<Awaited<ReturnType<typeof client.client.complete.detail.$post>>>
          >
        >,
        TError,
        InferRequestType<typeof client.client.complete.detail.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientCompleteDetailMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientHoverMutationKey() {
  return ['client', '/client/hover', 'POST'] as const
}

export function getPostClientHoverMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.hover.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.hover.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientHoverMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.hover.$post>) {
      return parseResponse(client.client.hover.$post(args, options))
    },
  })
}

export function usePostClientHover<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.hover.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.hover.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientHoverMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientSignatureMutationKey() {
  return ['client', '/client/signature', 'POST'] as const
}

export function getPostClientSignatureMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.signature.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.signature.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientSignatureMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.signature.$post>) {
      return parseResponse(client.client.signature.$post(args, options))
    },
  })
}

export function usePostClientSignature<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<
            typeof parseResponse<Awaited<ReturnType<typeof client.client.signature.$post>>>
          >
        >,
        TError,
        InferRequestType<typeof client.client.signature.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientSignatureMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientFormatMutationKey() {
  return ['client', '/client/format', 'POST'] as const
}

export function getPostClientFormatMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.format.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.format.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientFormatMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.format.$post>) {
      return parseResponse(client.client.format.$post(args, options))
    },
  })
}

export function usePostClientFormat<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.format.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.format.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientFormatMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientPreviewMutationKey() {
  return ['client', '/client/preview', 'POST'] as const
}

export function getPostClientPreviewMutationOptions<
  TError = DefaultError,
  TOnMutateResult = unknown,
>(options?: ClientRequestOptions) {
  return mutationOptions<
    Awaited<
      ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.preview.$post>>>>
    >,
    TError,
    InferRequestType<typeof client.client.preview.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientPreviewMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.preview.$post>) {
      return parseResponse(client.client.preview.$post(args, options))
    },
  })
}

export function usePostClientPreview<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.preview.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.preview.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientPreviewMutationOptions<TError, TOnMutateResult>(
    clientOptions,
  )
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getPostClientRunMutationKey() {
  return ['client', '/client/run', 'POST'] as const
}

export function getPostClientRunMutationOptions<TError = DefaultError, TOnMutateResult = unknown>(
  options?: ClientRequestOptions,
) {
  return mutationOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.run.$post>>>>>,
    TError,
    InferRequestType<typeof client.client.run.$post>,
    TOnMutateResult
  >({
    mutationKey: getPostClientRunMutationKey(),
    async mutationFn(args: InferRequestType<typeof client.client.run.$post>) {
      return parseResponse(client.client.run.$post(args, options))
    },
  })
}

export function usePostClientRun<TError = DefaultError, TOnMutateResult = unknown>(
  options?: {
    mutation?: Omit<
      UseMutationOptions<
        Awaited<
          ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.client.run.$post>>>>
        >,
        TError,
        InferRequestType<typeof client.client.run.$post>,
        TOnMutateResult
      >,
      'mutationFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { mutation: mutationOptions, options: clientOptions } = options ?? {}
  const mutationDefaults = getPostClientRunMutationOptions<TError, TOnMutateResult>(clientOptions)
  return useMutation(
    {
      ...mutationOptions,
      ...mutationDefaults,
      mutationKey: mutationOptions?.mutationKey ?? mutationDefaults.mutationKey,
    },
    queryClient,
  )
}

export function getDocsQueryKey() {
  return ['docs', '/docs'] as const
}

export function getDocsQueryOptions<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
  TError = DefaultError,
>(options?: ClientRequestOptions) {
  return queryOptions<
    Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
    TError,
    TData,
    ReturnType<typeof getDocsQueryKey>
  >({
    queryKey: getDocsQueryKey(),
    queryFn({ signal }) {
      return parseResponse(
        client.docs.$get(undefined, { ...options, init: { ...options?.init, signal } }),
      )
    },
  })
}

export function useDocs<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getDocsQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useQuery(
    { ...getDocsQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}

export function useSuspenseDocs<
  TData = Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
  TError = DefaultError,
>(
  options?: {
    query?: Omit<
      UseSuspenseQueryOptions<
        Awaited<ReturnType<typeof parseResponse<Awaited<ReturnType<typeof client.docs.$get>>>>>,
        TError,
        TData,
        ReturnType<typeof getDocsQueryKey>
      >,
      'queryKey' | 'queryFn'
    >
    options?: ClientRequestOptions
  },
  queryClient?: QueryClient,
) {
  const { query: queryOptions, options: clientOptions } = options ?? {}
  return useSuspenseQuery(
    { ...getDocsQueryOptions<TData, TError>(clientOptions), ...queryOptions },
    queryClient,
  )
}
