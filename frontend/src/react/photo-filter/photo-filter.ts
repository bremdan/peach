/* 写真筛选的数据契约：参考对象、上传、筛选任务、结果与设置。
 *
 * 端点在这里各声明一次；页面只取这里的函数与类型。打分、分层与向量构建全在服务层，
 * 页面只负责把任务的进度与结果摆出来，不重算分数或层名。
 *
 * 阈值是任务参数（`photo_filter_task` 自带列），不另存一份偏好；模型目录走
 * `[photo_filter] model_root`，与第 2 步的设置是同一份。
 */
import { apiGet, apiSend } from '../../api';
import { queryClient } from '../query';

export const PHOTO_FILTER_REFERENCES = ['photo-filter', 'references'] as const;
export const PHOTO_FILTER_SETTINGS = ['photo-filter', 'settings'] as const;
export const PHOTO_FILTER_TASKS = ['photo-filter', 'tasks'] as const;
export const photoFilterTaskKey = (id: number) => ['photo-filter', 'task', id] as const;

export const MIN_REFERENCE_PHOTOS = 5;
export const MAX_REFERENCE_PHOTOS = 15;
export const MIN_VALID_FACES = 3;
export const DEFAULT_HIT_THRESHOLD = 0.5;
export const DEFAULT_TASTE_THRESHOLD = 0.3;

export type ReferenceStatus = 'ready' | 'failed';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type Tier = 'hit' | 'suspected' | 'taste' | 'miss' | 'insufficient' | 'failed';

export interface PhotoFilterReference {
  id: number;
  name: string;
  valid_face_count: number;
  status: ReferenceStatus;
  failure_reason: string;
  provider: string;
  created_at: string;
  updated_at: string;
}

export interface PhotoFilterSettings {
  model_root: string;
  model_root_resolved: string;
  model_ready: boolean;
  runtime_available: boolean;
  cuda_available: boolean;
}

export interface PhotoFilterTask {
  id: number;
  root_path: string;
  status: TaskStatus;
  processed_count: number;
  total_count: number;
  hit_threshold: number;
  taste_threshold: number;
  created_at: string;
  updated_at: string;
  result_count?: number;
}

export interface PhotoFilterResult {
  id: number;
  album_path: string;
  album_name: string;
  score: number;
  top_reference_id: number | null;
  top_reference_name: string;
  valid_image_count: number;
  total_image_count: number;
  protagonist_cluster_ratio: number;
  tier: Tier;
  tier_label: string;
  protagonist_spread: boolean;
  failure_reason: string;
  face_url: string;
}

export interface PhotoFilterTaskDetail {
  task: PhotoFilterTask;
  results: PhotoFilterResult[];
}

export const fetchReferences = (signal?: AbortSignal) =>
  apiGet<{ references: PhotoFilterReference[] }>('/api/photo-filter/references', signal);

export const fetchSettings = (signal?: AbortSignal) =>
  apiGet<PhotoFilterSettings>('/api/photo-filter/settings', signal);

export const fetchTasks = (signal?: AbortSignal) =>
  apiGet<{ tasks: PhotoFilterTask[] }>('/api/photo-filter/tasks', signal);

export const fetchTask = (id: number, signal?: AbortSignal) =>
  apiGet<PhotoFilterTaskDetail>(`/api/photo-filter/tasks/${id}`, signal);

export const createUpload = () =>
  apiSend<{ token: string }>('/api/photo-filter/uploads', {});

export const deleteUpload = (token: string) =>
  apiSend<{ ok: boolean }>(`/api/photo-filter/uploads/${token}`, {}, 'DELETE');

/** 一张参考照片原样当请求体发，文件名走请求头；与口味导入同一个理由，不引入 multipart。 */
export async function uploadPhoto(token: string, file: File): Promise<void> {
  const response = await fetch(`/api/photo-filter/uploads/${token}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-Peach-Filename': encodeURIComponent(file.name),
    },
    body: file,
  });
  if (!response.ok) {
    let payload: unknown = null;
    try { payload = await response.json() } catch { /* 失败响应不一定是 JSON */ }
    throw new Error((payload as { error?: string } | null)?.error || `upload failed (${response.status})`);
  }
}

export const createReference = (name: string, uploadToken: string) =>
  apiSend<PhotoFilterReference>('/api/photo-filter/references', { name, upload_token: uploadToken });

export const rebuildReference = (id: number) =>
  apiSend<PhotoFilterReference>(`/api/photo-filter/references/${id}/rebuild`, {});

export const deleteReference = (id: number) =>
  apiSend<{ ok: boolean }>(`/api/photo-filter/references/${id}`, {}, 'DELETE');

export const saveSettings = (modelRoot: string) =>
  apiSend<PhotoFilterSettings>('/api/photo-filter/settings', { model_root: modelRoot });

export const createTask = (body: { root_path: string; hit_threshold: number; taste_threshold: number }) =>
  apiSend<PhotoFilterTask>('/api/photo-filter/tasks', body);

export const cancelTask = (id: number) =>
  apiSend<PhotoFilterTask>(`/api/photo-filter/tasks/${id}/cancel`, {});

export const revealResult = (resultId: number) =>
  apiSend<{ ok: boolean; path?: string; mode?: string }>('/api/photo-filter/reveal', { result_id: resultId });

/** 选图集根目录：复用配置页那条本机选择器。 */
export async function pickAlbumRoot(initial = ''): Promise<string | null> {
  const out = await apiSend<{ path?: string | null }>('/api/pick-folder', { initial, purpose: 'media' });
  return out.path ?? null;
}

/** 首屏：参考对象、设置与历史一起取齐。 */
export async function prefetchPhotoFilter(signal: AbortSignal): Promise<void> {
  await Promise.all([
    queryClient.fetchQuery({
      queryKey: PHOTO_FILTER_REFERENCES, queryFn: () => fetchReferences(signal),
    }),
    queryClient.fetchQuery({
      queryKey: PHOTO_FILTER_SETTINGS, queryFn: () => fetchSettings(signal),
    }),
    queryClient.fetchQuery({
      queryKey: PHOTO_FILTER_TASKS, queryFn: () => fetchTasks(signal),
    }),
  ]);
}

export const isRunning = (task: PhotoFilterTask | undefined): boolean =>
  task?.status === 'pending' || task?.status === 'running';

export const albumName = (path: string): string =>
  path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || path;

export const percent = (value: number): string => `${Math.round(value * 100)}%`;
