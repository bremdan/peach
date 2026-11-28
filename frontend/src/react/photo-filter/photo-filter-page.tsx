/* 写真筛选页：参考对象、筛选任务、三层榜单与历史。
 *
 * 认人为主、口味为辅：榜单一律按服务层给的层名显示，不把「口味相似」说成命中。
 * 「疑似命中·待确认」与「信号不足」各自成区，不埋进命中列表；主角簇占比不足一半的
 * 卡片只在层名后加注，不改分数。点卡片只在本机文件管理器里定位图集目录，不动任何文件。
 */
import { useEffect, useRef, useState } from 'react';
import {
  RiDeleteBinLine, RiFolderOpenLine, RiPlayLine, RiRefreshLine, RiStopCircleLine, RiUploadLine,
} from '@remixicon/react';
import { useMutation, useQuery } from '@tanstack/react-query';

import { confirmModal } from '@peach/legacy/ui';

import { Button } from '@/components/base/buttons/button';
import { Input } from '@/components/base/input/input';

import { errorMessage } from '../../api';
import { t } from '../../i18n';
import { cardClass } from '../components/card';
import { EmptyState } from '../components/empty-state';
import { Note } from '../components/note';
import { Page } from '../components/page';
import { TaskProgress } from '../components/task-progress';
import { queryClient } from '../query';
import {
  albumName, cancelTask, createReference, createTask, createUpload, DEFAULT_HIT_THRESHOLD,
  DEFAULT_TASTE_THRESHOLD, deleteReference, deleteUpload, fetchReferences, fetchSettings, fetchTask,
  fetchTasks, isRunning, MAX_REFERENCE_PHOTOS, MIN_REFERENCE_PHOTOS, MIN_VALID_FACES, percent,
  PHOTO_FILTER_REFERENCES, PHOTO_FILTER_SETTINGS, PHOTO_FILTER_TASKS, photoFilterTaskKey,
  pickAlbumRoot, rebuildReference, revealResult, saveSettings, uploadPhoto,
  type PhotoFilterReference, type PhotoFilterResult, type PhotoFilterSettings, type PhotoFilterTask,
  type PhotoFilterTaskDetail, type Tier,
} from './photo-filter';

const CARD = cardClass();
const SUBTITLE = 'text-caption-1-regular text-text-secondary';

const TIER_LABELS: Record<Tier, string> = {
  hit: t('manage:photoFilter.tierHit'),
  suspected: t('manage:photoFilter.tierSuspected'),
  taste: t('manage:photoFilter.tierTaste'),
  miss: t('manage:photoFilter.tierMiss'),
  insufficient: t('manage:photoFilter.tierInsufficient'),
  failed: t('manage:photoFilter.tierFailed'),
};

const resultName = (result: PhotoFilterResult): string =>
  result.album_name || albumName(result.album_path);

const STATUS_LABELS: Record<string, string> = {
  ready: t('manage:photoFilter.statusReady'),
  failed: t('manage:photoFilter.statusFailed'),
  pending: t('manage:photoFilter.statusPending'),
  running: t('manage:photoFilter.statusRunning'),
  completed: t('manage:photoFilter.statusCompleted'),
  cancelled: t('manage:photoFilter.statusCancelled'),
};

const statusLabel = (status: string): string => STATUS_LABELS[status] ?? status;

export function PhotoFilterPage({ toast }: { toast?: (message: string) => void }) {
  const references = useQuery({
    queryKey: PHOTO_FILTER_REFERENCES,
    queryFn: ({ signal }) => fetchReferences(signal),
  });
  const settings = useQuery({
    queryKey: PHOTO_FILTER_SETTINGS,
    queryFn: ({ signal }) => fetchSettings(signal),
  });
  const tasks = useQuery({
    queryKey: PHOTO_FILTER_TASKS,
    queryFn: ({ signal }) => fetchTasks(signal),
    refetchInterval: (query) => query.state.data?.tasks.some(isRunning) ? 1500 : false,
  });
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const taskList = tasks.data?.tasks ?? [];
  const activeTaskId = selectedTaskId ?? taskList[taskList.length - 1]?.id ?? null;
  const detail = useQuery<PhotoFilterTaskDetail>({
    queryKey: activeTaskId ? photoFilterTaskKey(activeTaskId) : ['photo-filter', 'task', 'none'],
    queryFn: ({ signal }) => fetchTask(activeTaskId as number, signal),
    enabled: activeTaskId != null,
    refetchInterval: (query) => isRunning(query.state.data?.task) ? 1000 : false,
  });

  const notify = (message: string) => toast?.(message);

  return (
    <Page>
      <SettingsCard settings={settings.data} error={settings.error} notify={notify} />
      <ReferencesCard references={references.data?.references ?? []} error={references.error} notify={notify} />
      <NewTaskCard
        onStarted={(task) => {
          setSelectedTaskId(task.id);
          void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_TASKS });
        }}
        notify={notify}
        settings={settings.data}
      />
      <TaskSection
        task={detail.data?.task}
        detail={detail.data}
        loading={detail.isPending && activeTaskId != null}
        error={detail.error}
        notify={notify}
      />
      <HistoryCard
        tasks={taskList}
        selected={activeTaskId}
        error={tasks.error}
        onSelect={setSelectedTaskId}
        notify={notify}
      />
    </Page>
  );
}

function SectionHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-title-2-medium text-text-primary">{title}</h3>
      {children}
    </header>
  );
}

function SettingsCard({ settings, error, notify }: {
  settings?: PhotoFilterSettings; error: unknown; notify: (message: string) => void;
}) {
  const [modelRoot, setModelRoot] = useState('');
  useEffect(() => { if (settings) setModelRoot(settings.model_root) }, [settings?.model_root]);
  const save = useMutation({
    mutationFn: () => saveSettings(modelRoot),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_SETTINGS });
      notify(t('manage:photoFilter.settingsSaved'));
    },
  });
  const choose = async () => {
    try {
      const path = await pickAlbumRoot(modelRoot);
      if (path) setModelRoot(path);
    } catch (cause) {
      notify(errorMessage(cause));
    }
  };
  return (
    <section className={CARD} aria-label={t('manage:photoFilter.settingsTitle')}>
      <SectionHeader title={t('manage:photoFilter.settingsTitle')} />
      {error ? <Note tone="error">{errorMessage(error)}</Note> : null}
      <div className="flex flex-col gap-2">
        <span className="text-body-2-medium text-text-primary">{t('manage:photoFilter.modelDirectory')}</span>
        <div className="flex flex-wrap items-center gap-2">
          <Input aria-label={t('manage:photoFilter.modelDirectory')} value={modelRoot}
            placeholder={t('manage:photoFilter.modelPlaceholder')}
            onChange={setModelRoot} className="min-w-48 grow" />
          <Button size="small" variant="secondary" leadingIcon={RiFolderOpenLine} onClick={() => void choose()}>
            {t('manage:photoFilter.chooseFolder')}
          </Button>
          <Button size="small" variant="primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {t('manage:photoFilter.save')}
          </Button>
        </div>
        {settings ? (
          settings.model_ready
            ? <p className={SUBTITLE}>{t('manage:photoFilter.modelReady', { path: settings.model_root_resolved })}</p>
            : <Note tone="warning" title={t('manage:photoFilter.modelMissingTitle')}>
                {t('manage:photoFilter.modelMissingHint', { path: settings.model_root_resolved })}
              </Note>
        ) : null}
        {settings && !settings.runtime_available
          ? <Note tone="warning">{t('manage:photoFilter.runtimeMissing')}</Note> : null}
        {settings && settings.runtime_available && !settings.cuda_available
          ? <Note tone="info">{t('manage:photoFilter.cpuFallback')}</Note> : null}
        {save.error ? <Note tone="error">{errorMessage(save.error)}</Note> : null}
      </div>
    </section>
  );
}

function ReferencesCard({ references, error, notify }: {
  references: PhotoFilterReference[]; error: unknown; notify: (message: string) => void;
}) {
  const [name, setName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const create = useMutation({
    mutationFn: async () => {
      const chosen = files;
      if (chosen.length < MIN_REFERENCE_PHOTOS || chosen.length > MAX_REFERENCE_PHOTOS) {
        throw new Error(t('manage:photoFilter.photoCount', { min: MIN_REFERENCE_PHOTOS, max: MAX_REFERENCE_PHOTOS }));
      }
      const { token } = await createUpload();
      try {
        for (const [index, file] of chosen.entries()) {
          setUploading(t('manage:photoFilter.uploading', { done: index + 1, total: chosen.length }));
          await uploadPhoto(token, file);
        }
        return await createReference(name, token);
      } catch (cause) {
        await deleteUpload(token).catch(() => {});
        throw cause;
      } finally {
        setUploading('');
      }
    },
    onSuccess: (reference) => {
      setName(''); setFiles([]);
      if (input.current) input.current.value = '';
      void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_REFERENCES });
      notify(reference.status === 'ready'
        ? t('manage:photoFilter.referenceCreated', { count: reference.valid_face_count })
        : t('manage:photoFilter.insufficientFaces', { count: reference.valid_face_count, needed: MIN_VALID_FACES }));
    },
  });
  const rebuild = useMutation({
    mutationFn: (id: number) => rebuildReference(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_REFERENCES }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => deleteReference(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_REFERENCES }),
  });
  const pick = (chosen: File[]) => setFiles(chosen.slice(0, MAX_REFERENCE_PHOTOS + 5));
  const askDelete = (reference: PhotoFilterReference) => {
    void confirmModal({
      title: t('manage:photoFilter.deleteReference'),
      body: t('manage:photoFilter.deleteReferenceBody', { name: reference.name }),
      confirmLabel: t('manage:photoFilter.deleteReference'),
      holdToConfirm: true,
      onConfirm: () => remove.mutateAsync(reference.id),
    });
  };
  return (
    <section className={CARD} aria-label={t('manage:photoFilter.referencesTitle')}>
      <SectionHeader title={t('manage:photoFilter.referencesTitle')} />
      <Note tone="info">{t('manage:photoFilter.sameDomainHint')}</Note>
      {error ? <Note tone="error">{errorMessage(error)}</Note> : null}
      <div className="flex flex-col gap-3">
        <span className="text-body-2-medium text-text-primary">{t('manage:photoFilter.newReference')}</span>
        <div className="flex flex-wrap items-end gap-2">
          <Input label={t('manage:photoFilter.name')} value={name} onChange={setName}
            className="min-w-40 grow" />
          <input ref={input} type="file" multiple accept="image/jpeg,image/png,image/webp,image/bmp"
            tabIndex={-1} aria-hidden className="hidden"
            onChange={(event) => pick(Array.from(event.currentTarget.files ?? []))} />
          <Button size="small" variant="secondary" leadingIcon={RiUploadLine}
            onClick={() => input.current?.click()}>
            {t('manage:photoFilter.choosePhotos')}
          </Button>
          <Button size="small" variant="primary" disabled={create.isPending || !name.trim() || !files.length}
            onClick={() => create.mutate()}>
            {t('manage:photoFilter.buildVector')}
          </Button>
        </div>
        <p className={SUBTITLE}>{t('manage:photoFilter.photoCountHint', {
          min: MIN_REFERENCE_PHOTOS, max: MAX_REFERENCE_PHOTOS, count: files.length,
        })}</p>
        {uploading ? <p className={SUBTITLE}>{uploading}</p> : null}
        {create.error ? <Note tone="error">{errorMessage(create.error)}</Note> : null}
      </div>
      {references.length ? (
        <ul className="flex flex-col gap-2">
          {references.map((reference) => (
            <li key={reference.id} className="flex flex-wrap items-center gap-3 rounded-xl bg-background-primary-default p-3">
              <span className="flex min-w-0 grow flex-col gap-0.5">
                <b className="min-w-0 text-body-medium break-words text-text-primary">{reference.name}</b>
                <small className={SUBTITLE}>{t('manage:photoFilter.validFaces', { count: reference.valid_face_count })}
                  {' · '}{statusLabel(reference.status)}
                  {reference.status === 'failed'
                    ? ` · ${t('manage:photoFilter.addMorePhotos', { needed: MIN_VALID_FACES })}` : ''}
                </small>
              </span>
              <Button size="small" variant="secondary" leadingIcon={RiRefreshLine}
                disabled={rebuild.isPending} onClick={() => rebuild.mutate(reference.id)}>
                {t('manage:photoFilter.rebuildVector')}
              </Button>
              <Button size="small" variant="secondary" iconOnly leadingIcon={RiDeleteBinLine}
                aria-label={t('manage:photoFilter.deleteReference')}
                disabled={remove.isPending} onClick={() => askDelete(reference)} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState size="compact" icon={RiUploadLine} title={t('manage:photoFilter.noReferences')}>
          {t('manage:photoFilter.noReferencesHint')}
        </EmptyState>
      )}
    </section>
  );
}

function NewTaskCard({ onStarted, notify, settings }: {
  onStarted: (task: PhotoFilterTask) => void; notify: (message: string) => void;
  settings?: PhotoFilterSettings;
}) {
  const [rootPath, setRootPath] = useState('');
  const [hit, setHit] = useState(String(DEFAULT_HIT_THRESHOLD));
  const [taste, setTaste] = useState(String(DEFAULT_TASTE_THRESHOLD));
  const start = useMutation({
    mutationFn: () => createTask({
      root_path: rootPath.trim(),
      hit_threshold: Number(hit),
      taste_threshold: Number(taste),
    }),
    onSuccess: (task) => {
      onStarted(task);
      notify(t('manage:photoFilter.taskStarted'));
    },
  });
  const choose = async () => {
    try {
      const path = await pickAlbumRoot(rootPath);
      if (path) setRootPath(path);
    } catch (cause) {
      notify(errorMessage(cause));
    }
  };
  const missingModel = settings ? !settings.model_ready : false;
  return (
    <section className={CARD} aria-label={t('manage:photoFilter.newTask')}>
      <SectionHeader title={t('manage:photoFilter.newTask')} />
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <Input label={t('manage:photoFilter.albumRoot')} value={rootPath} onChange={setRootPath}
            placeholder={t('manage:photoFilter.albumRootPlaceholder')} className="min-w-48 grow" />
          <Button size="small" variant="secondary" leadingIcon={RiFolderOpenLine} onClick={() => void choose()}>
            {t('manage:photoFilter.chooseFolder')}
          </Button>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Input label={t('manage:photoFilter.hitThreshold')} type="number" inputMode="decimal" value={hit} onChange={setHit} className="w-36" />
          <Input label={t('manage:photoFilter.tasteThreshold')} type="number" inputMode="decimal" value={taste} onChange={setTaste} className="w-36" />
          <Button size="small" variant="primary" leadingIcon={RiPlayLine}
            disabled={start.isPending || missingModel || !rootPath.trim()}
            onClick={() => start.mutate()}>
            {t('manage:photoFilter.startFilter')}
          </Button>
        </div>
        <p className={SUBTITLE}>{t('manage:photoFilter.thresholdHint', {
          hit: DEFAULT_HIT_THRESHOLD, taste: DEFAULT_TASTE_THRESHOLD,
        })}</p>
        {missingModel ? <Note tone="warning">{t('manage:photoFilter.modelRequired')}</Note> : null}
        {start.error ? <Note tone="error">{errorMessage(start.error)}</Note> : null}
      </div>
    </section>
  );
}

function TaskSection({ task, detail, loading, error, notify }: {
  task?: PhotoFilterTask; detail?: PhotoFilterTaskDetail; loading: boolean; error: unknown;
  notify: (message: string) => void;
}) {
  const cancel = useMutation({
    mutationFn: (id: number) => cancelTask(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PHOTO_FILTER_TASKS });
      notify(t('manage:photoFilter.taskCancelled'));
    },
  });
  if (loading) {
    return <section className={CARD}><TaskProgress kind="gather" label={t('manage:photoFilter.loadingResults')} /></section>;
  }
  if (error) {
    return <section className={CARD}><Note tone="error">{errorMessage(error)}</Note></section>;
  }
  if (!task || !detail) {
    return (
      <section className={CARD} aria-label={t('manage:photoFilter.resultsTitle')}>
        <SectionHeader title={t('manage:photoFilter.resultsTitle')} />
        <EmptyState size="compact" icon={RiPlayLine} title={t('manage:photoFilter.noTask')}>
          {t('manage:photoFilter.noTaskHint')}
        </EmptyState>
      </section>
    );
  }
  const main = detail.results.filter((result) =>
    result.tier !== 'suspected' && result.tier !== 'insufficient' && result.tier !== 'failed');
  const suspected = detail.results.filter((result) => result.tier === 'suspected');
  const insufficient = detail.results.filter((result) => result.tier === 'insufficient');
  const failed = detail.results.filter((result) => result.tier === 'failed');
  return (
    <section className={CARD} aria-label={t('manage:photoFilter.resultsTitle')}>
      <SectionHeader title={t('manage:photoFilter.resultsTitle')}>
        {isRunning(task) ? (
          <Button size="small" variant="secondary" leadingIcon={RiStopCircleLine}
            disabled={cancel.isPending} onClick={() => cancel.mutate(task.id)}>
            {t('manage:photoFilter.cancel')}
          </Button>
        ) : null}
      </SectionHeader>
      <p className={SUBTITLE}>{t('manage:photoFilter.taskSummary', {
        root: task.root_path, status: statusLabel(task.status),
        done: task.processed_count, total: task.total_count,
      })}</p>
      {isRunning(task) ? (
        <TaskProgress kind="radar" label={t('manage:photoFilter.progress', {
          done: task.processed_count, total: task.total_count,
        })} value={task.processed_count} total={task.total_count} />
      ) : null}
      {task.status === 'failed' ? <Note tone="error">{t('manage:photoFilter.taskFailed')}</Note> : null}
      {task.status === 'cancelled' ? <Note tone="warning">{t('manage:photoFilter.taskWasCancelled')}</Note> : null}
      {cancel.error ? <Note tone="error">{errorMessage(cancel.error)}</Note> : null}

      {failed.length ? (
        <div className="flex flex-col gap-2">
          <h4 className="text-body-semibold text-text-primary">{t('manage:photoFilter.zoneFailed')}</h4>
          <ul className="flex flex-col gap-1">
            {failed.map((result) => (
              <li key={result.id} className="flex flex-wrap items-baseline gap-2 text-body-2-regular text-text-secondary">
                <span className="min-w-0 break-words text-text-primary">{resultName(result)}</span>
                <span>{result.failure_reason || result.tier_label}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {main.length ? (
        <div className="flex flex-col gap-3">
          <h4 className="text-body-semibold text-text-primary">{t('manage:photoFilter.zoneHits')}</h4>
          <div className="inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {main.map((result) => <ResultCard key={result.id} result={result} notify={notify} />)}
          </div>
        </div>
      ) : detail.results.length ? null : (
        <EmptyState size="compact" icon={RiPlayLine} title={t('manage:photoFilter.noResults')}>
          {t('manage:photoFilter.noResultsHint')}
        </EmptyState>
      )}

      {suspected.length ? (
        <div className="flex flex-col gap-3">
          <h4 className="text-body-semibold text-text-primary">{t('manage:photoFilter.zoneSuspected')}</h4>
          <div className="inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {suspected.map((result) => <ResultCard key={result.id} result={result} notify={notify} suspected />)}
          </div>
        </div>
      ) : null}

      {insufficient.length ? (
        <div className="flex flex-col gap-2">
          <h4 className="text-body-semibold text-text-primary">{t('manage:photoFilter.zoneInsufficient')}</h4>
          <ul className="flex flex-col gap-1">
            {insufficient.map((result) => (
              <li key={result.id} className="flex flex-wrap items-baseline gap-2 text-body-2-regular text-text-secondary">
                <span className="min-w-0 break-words text-text-primary">{resultName(result)}</span>
                <span>{t('manage:photoFilter.validImages', { count: result.valid_image_count })}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function ResultCard({ result, notify, suspected = false }: {
  result: PhotoFilterResult; notify: (message: string) => void; suspected?: boolean;
}) {
  const open = async () => {
    try {
      const position = await revealResult(result.id);
      notify(position.mode === 'server' && position.path
        ? t('manage:photoFilter.revealedServer', { path: position.path })
        : t('manage:photoFilter.revealed'));
    } catch (cause) {
      notify(errorMessage(cause));
    }
  };
  return (
    <button type="button" onClick={() => void open()}
      className="flex min-w-0 cursor-pointer flex-col gap-3 rounded-xl bg-background-primary-default p-3 text-left outline-none hover:bg-background-primary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring">
      <div className="flex gap-3">
        {result.face_url
          ? <img src={result.face_url} alt="" loading="lazy"
              className="size-16 shrink-0 rounded-lg bg-media-placeholder object-cover" />
          : <span className="size-16 shrink-0 rounded-lg bg-media-placeholder" />}
        <span className="flex min-w-0 flex-col gap-0.5">
          <b className="min-w-0 text-body-medium break-words text-text-primary">{resultName(result)}</b>
          <small className={SUBTITLE}>{TIER_LABELS[result.tier]}</small>
          <small className={SUBTITLE}>{t('manage:photoFilter.score', { score: result.score.toFixed(3) })}</small>
        </span>
      </div>
      {suspected ? (
        <span className="rounded-lg bg-status-yellow-background px-2 py-1 text-caption-1-medium text-status-yellow-text">
          {t('manage:photoFilter.suspectedMarker')}
        </span>
      ) : null}
      <dl className="inline-grid w-full grid-cols-2 gap-x-3 gap-y-1 text-caption-1-regular text-text-secondary">
        <dt>{t('manage:photoFilter.topReference')}</dt>
        <dd className="min-w-0 truncate text-right text-text-primary">
          {result.top_reference_name || t('manage:photoFilter.noReference')}
        </dd>
        <dt>{t('manage:photoFilter.images')}</dt>
        <dd className="text-right tabular-nums text-text-primary">
          {result.valid_image_count} / {result.total_image_count}
        </dd>
        <dt>{t('manage:photoFilter.protagonistShare')}</dt>
        <dd className="text-right tabular-nums text-text-primary">{percent(result.protagonist_cluster_ratio)}</dd>
      </dl>
      {result.protagonist_spread
        ? <span className="text-caption-1-regular text-status-yellow-text">{t('manage:photoFilter.protagonistSpread')}</span>
        : null}
    </button>
  );
}

function HistoryCard({ tasks, selected, error, onSelect, notify }: {
  tasks: PhotoFilterTask[]; selected: number | null; error: unknown;
  onSelect: (id: number) => void; notify: (message: string) => void;
}) {
  return (
    <section className={CARD} aria-label={t('manage:photoFilter.historyTitle')}>
      <SectionHeader title={t('manage:photoFilter.historyTitle')} />
      {error ? <Note tone="error">{errorMessage(error)}</Note> : null}
      {tasks.length ? (
        <ul className="flex flex-col gap-2">
          {[...tasks].reverse().map((task) => (
            <li key={task.id}>
              <button type="button" onClick={() => { onSelect(task.id); notify(t('manage:photoFilter.historyOpened')) }}
                aria-current={task.id === selected ? 'true' : undefined}
                className={`flex w-full min-w-0 flex-col gap-1 rounded-xl p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring ${
                  task.id === selected ? 'bg-background-primary-hover' : 'bg-background-primary-default hover:bg-background-primary-hover'}`}>
                <span className="flex min-w-0 flex-wrap items-baseline gap-2">
                  <b className="min-w-0 break-words text-body-2-medium text-text-primary">{task.root_path}</b>
                  <small className={SUBTITLE}>{statusLabel(task.status)}</small>
                </span>
                <small className={SUBTITLE}>{t('manage:photoFilter.historySummary', {
                  done: task.processed_count, total: task.total_count,
                  count: task.result_count ?? 0,
                })}</small>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState size="compact" icon={RiPlayLine} title={t('manage:photoFilter.noHistory')}>
          {t('manage:photoFilter.noHistoryHint')}
        </EmptyState>
      )}
    </section>
  );
}
