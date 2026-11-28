(function() {
	try {
		var e = typeof globalThis < "u" ? globalThis : typeof window < "u" ? window : typeof global < "u" ? global : typeof self < "u" ? self : {}, t = new e.Error().stack;
		t && (e._sentryDebugIds = e._sentryDebugIds || {}, e._sentryDebugIds[t] = "b445d6ba-b7dd-4a8c-a0be-500988ca5140", e._sentryDebugIdIdentifier = "sentry-dbid-b445d6ba-b7dd-4a8c-a0be-500988ca5140");
	} catch {}
})();
import { Button as e, DEFAULT_HIT_THRESHOLD as t, DEFAULT_TASTE_THRESHOLD as n, EmptyState as r, Gg as i, Input as a, LN as o, M6 as s, Note as c, PHOTO_FILTER_REFERENCES as l, PHOTO_FILTER_SETTINGS as u, PHOTO_FILTER_TASKS as d, Rf as f, TaskProgress as p, __toESM as m, albumName as h, cancelTask as g, cardClass as _, confirmModal as v, createReference as y, createTask as b, createUpload as x, dZ as S, deleteReference as C, deleteUpload as w, errorMessage as T, fetchReferences as E, fetchSettings as D, fetchTask as O, fetchTasks as k, isRunning as A, percent as j, photoFilterTaskKey as M, pickAlbumRoot as N, queryClient as P, rebuildReference as F, require_jsx_runtime as ee, require_react as te, revealResult as ne, saveSettings as I, t as L, uploadPhoto as R, useMutation as z, useQuery as B, xs as V } from "./peach-app.js";
import { Page as H } from "./peach-app.page-QAncjzM1.js";
// src/react/photo-filter/photo-filter-page.tsx
var U = /* @__PURE__ */ m(te(), 1), W = ee(), G = _(), K = "text-caption-1-regular text-text-secondary", q = {
	hit: L("manage:photoFilter.tierHit"),
	suspected: L("manage:photoFilter.tierSuspected"),
	taste: L("manage:photoFilter.tierTaste"),
	miss: L("manage:photoFilter.tierMiss"),
	insufficient: L("manage:photoFilter.tierInsufficient"),
	failed: L("manage:photoFilter.tierFailed")
}, J = (e) => e.album_name || h(e.album_path), Y = {
	ready: L("manage:photoFilter.statusReady"),
	failed: L("manage:photoFilter.statusFailed"),
	pending: L("manage:photoFilter.statusPending"),
	running: L("manage:photoFilter.statusRunning"),
	completed: L("manage:photoFilter.statusCompleted"),
	cancelled: L("manage:photoFilter.statusCancelled")
}, X = (e) => Y[e] ?? e;
function Z({ toast: e }) {
	let t = B({
		queryKey: l,
		queryFn: ({ signal: e }) => E(e)
	}), n = B({
		queryKey: u,
		queryFn: ({ signal: e }) => D(e)
	}), r = B({
		queryKey: d,
		queryFn: ({ signal: e }) => k(e),
		refetchInterval: (e) => e.state.data?.tasks.some(A) ? 1500 : !1
	}), [i, a] = (0, U.useState)(null), o = r.data?.tasks ?? [], s = i ?? o[o.length - 1]?.id ?? null, c = B({
		queryKey: s ? M(s) : [
			"photo-filter",
			"task",
			"none"
		],
		queryFn: ({ signal: e }) => O(s, e),
		enabled: s != null,
		refetchInterval: (e) => A(e.state.data?.task) ? 1e3 : !1
	}), f = (t) => e?.(t);
	return /* @__PURE__ */ (0, W.jsxs)(H, { children: [
		/* @__PURE__ */ (0, W.jsx)(re, {
			settings: n.data,
			error: n.error,
			notify: f
		}),
		/* @__PURE__ */ (0, W.jsx)(ie, {
			references: t.data?.references ?? [],
			error: t.error,
			notify: f
		}),
		/* @__PURE__ */ (0, W.jsx)(ae, {
			onStarted: (e) => {
				a(e.id), P.invalidateQueries({ queryKey: d });
			},
			notify: f,
			settings: n.data
		}),
		/* @__PURE__ */ (0, W.jsx)(oe, {
			task: c.data?.task,
			detail: c.data,
			loading: c.isPending && s != null,
			error: c.error,
			notify: f
		}),
		/* @__PURE__ */ (0, W.jsx)(se, {
			tasks: o,
			selected: s,
			error: r.error,
			onSelect: a,
			notify: f
		})
	] });
}
function Q({ title: e, children: t }) {
	return /* @__PURE__ */ (0, W.jsxs)("header", {
		className: "flex flex-wrap items-center justify-between gap-3",
		children: [/* @__PURE__ */ (0, W.jsx)("h3", {
			className: "text-title-2-medium text-text-primary",
			children: e
		}), t]
	});
}
function re({ settings: t, error: n, notify: r }) {
	let [i, o] = (0, U.useState)("");
	(0, U.useEffect)(() => {
		t && o(t.model_root);
	}, [t?.model_root]);
	let s = z({
		mutationFn: () => I(i),
		onSuccess: () => {
			P.invalidateQueries({ queryKey: u }), r(L("manage:photoFilter.settingsSaved"));
		}
	}), l = async () => {
		try {
			let e = await N(i);
			e && o(e);
		} catch (e) {
			r(T(e));
		}
	};
	return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.settingsTitle"),
		children: [
			/* @__PURE__ */ (0, W.jsx)(Q, { title: L("manage:photoFilter.settingsTitle") }),
			n ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "error",
				children: T(n)
			}) : null,
			/* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-2",
				children: [
					/* @__PURE__ */ (0, W.jsx)("span", {
						className: "text-body-2-medium text-text-primary",
						children: L("manage:photoFilter.modelDirectory")
					}),
					/* @__PURE__ */ (0, W.jsxs)("div", {
						className: "flex flex-wrap items-center gap-2",
						children: [
							/* @__PURE__ */ (0, W.jsx)(a, {
								"aria-label": L("manage:photoFilter.modelDirectory"),
								value: i,
								placeholder: L("manage:photoFilter.modelPlaceholder"),
								onChange: o,
								className: "min-w-48 grow"
							}),
							/* @__PURE__ */ (0, W.jsx)(e, {
								size: "small",
								variant: "secondary",
								leadingIcon: V,
								onClick: () => void l(),
								children: L("manage:photoFilter.chooseFolder")
							}),
							/* @__PURE__ */ (0, W.jsx)(e, {
								size: "small",
								variant: "primary",
								disabled: s.isPending,
								onClick: () => s.mutate(),
								children: L("manage:photoFilter.save")
							})
						]
					}),
					t ? t.model_ready ? /* @__PURE__ */ (0, W.jsx)("p", {
						className: K,
						children: L("manage:photoFilter.modelReady", { path: t.model_root_resolved })
					}) : /* @__PURE__ */ (0, W.jsx)(c, {
						tone: "warning",
						title: L("manage:photoFilter.modelMissingTitle"),
						children: L("manage:photoFilter.modelMissingHint", { path: t.model_root_resolved })
					}) : null,
					t && !t.runtime_available ? /* @__PURE__ */ (0, W.jsx)(c, {
						tone: "warning",
						children: L("manage:photoFilter.runtimeMissing")
					}) : null,
					t && t.runtime_available && !t.cuda_available ? /* @__PURE__ */ (0, W.jsx)(c, {
						tone: "info",
						children: L("manage:photoFilter.cpuFallback")
					}) : null,
					s.error ? /* @__PURE__ */ (0, W.jsx)(c, {
						tone: "error",
						children: T(s.error)
					}) : null
				]
			})
		]
	});
}
function ie({ references: t, error: n, notify: i }) {
	let [o, u] = (0, U.useState)(""), [d, p] = (0, U.useState)([]), [m, h] = (0, U.useState)(""), g = (0, U.useRef)(null), _ = z({
		mutationFn: async () => {
			let e = d;
			if (e.length < 5 || e.length > 15) throw Error(L("manage:photoFilter.photoCount", {
				min: 5,
				max: 15
			}));
			let { token: t } = await x();
			try {
				for (let [n, r] of e.entries()) h(L("manage:photoFilter.uploading", {
					done: n + 1,
					total: e.length
				})), await R(t, r);
				return await y(o, t);
			} catch (e) {
				throw await w(t).catch(() => {}), e;
			} finally {
				h("");
			}
		},
		onSuccess: (e) => {
			u(""), p([]), g.current && (g.current.value = ""), P.invalidateQueries({ queryKey: l }), i(e.status === "ready" ? L("manage:photoFilter.referenceCreated", { count: e.valid_face_count }) : L("manage:photoFilter.insufficientFaces", {
				count: e.valid_face_count,
				needed: 3
			}));
		}
	}), b = z({
		mutationFn: (e) => F(e),
		onSuccess: () => void P.invalidateQueries({ queryKey: l })
	}), E = z({
		mutationFn: (e) => C(e),
		onSuccess: () => void P.invalidateQueries({ queryKey: l })
	}), D = (e) => p(e.slice(0, 20)), O = (e) => {
		v({
			title: L("manage:photoFilter.deleteReference"),
			body: L("manage:photoFilter.deleteReferenceBody", { name: e.name }),
			confirmLabel: L("manage:photoFilter.deleteReference"),
			holdToConfirm: !0,
			onConfirm: () => E.mutateAsync(e.id)
		});
	};
	return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.referencesTitle"),
		children: [
			/* @__PURE__ */ (0, W.jsx)(Q, { title: L("manage:photoFilter.referencesTitle") }),
			/* @__PURE__ */ (0, W.jsx)(c, {
				tone: "info",
				children: L("manage:photoFilter.sameDomainHint")
			}),
			n ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "error",
				children: T(n)
			}) : null,
			/* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [
					/* @__PURE__ */ (0, W.jsx)("span", {
						className: "text-body-2-medium text-text-primary",
						children: L("manage:photoFilter.newReference")
					}),
					/* @__PURE__ */ (0, W.jsxs)("div", {
						className: "flex flex-wrap items-end gap-2",
						children: [
							/* @__PURE__ */ (0, W.jsx)(a, {
								label: L("manage:photoFilter.name"),
								value: o,
								onChange: u,
								className: "min-w-40 grow"
							}),
							/* @__PURE__ */ (0, W.jsx)("input", {
								ref: g,
								type: "file",
								multiple: !0,
								accept: "image/jpeg,image/png,image/webp,image/bmp",
								tabIndex: -1,
								"aria-hidden": !0,
								className: "hidden",
								onChange: (e) => D(Array.from(e.currentTarget.files ?? []))
							}),
							/* @__PURE__ */ (0, W.jsx)(e, {
								size: "small",
								variant: "secondary",
								leadingIcon: f,
								onClick: () => g.current?.click(),
								children: L("manage:photoFilter.choosePhotos")
							}),
							/* @__PURE__ */ (0, W.jsx)(e, {
								size: "small",
								variant: "primary",
								disabled: _.isPending || !o.trim() || !d.length,
								onClick: () => _.mutate(),
								children: L("manage:photoFilter.buildVector")
							})
						]
					}),
					/* @__PURE__ */ (0, W.jsx)("p", {
						className: K,
						children: L("manage:photoFilter.photoCountHint", {
							min: 5,
							max: 15,
							count: d.length
						})
					}),
					m ? /* @__PURE__ */ (0, W.jsx)("p", {
						className: K,
						children: m
					}) : null,
					_.error ? /* @__PURE__ */ (0, W.jsx)(c, {
						tone: "error",
						children: T(_.error)
					}) : null
				]
			}),
			t.length ? /* @__PURE__ */ (0, W.jsx)("ul", {
				className: "flex flex-col gap-2",
				children: t.map((t) => /* @__PURE__ */ (0, W.jsxs)("li", {
					className: "flex flex-wrap items-center gap-3 rounded-xl bg-background-primary-default p-3",
					children: [
						/* @__PURE__ */ (0, W.jsxs)("span", {
							className: "flex min-w-0 grow flex-col gap-0.5",
							children: [/* @__PURE__ */ (0, W.jsx)("b", {
								className: "min-w-0 text-body-medium break-words text-text-primary",
								children: t.name
							}), /* @__PURE__ */ (0, W.jsxs)("small", {
								className: K,
								children: [
									L("manage:photoFilter.validFaces", { count: t.valid_face_count }),
									" · ",
									X(t.status),
									t.status === "failed" ? ` · ${L("manage:photoFilter.addMorePhotos", { needed: 3 })}` : ""
								]
							})]
						}),
						/* @__PURE__ */ (0, W.jsx)(e, {
							size: "small",
							variant: "secondary",
							leadingIcon: S,
							disabled: b.isPending,
							onClick: () => b.mutate(t.id),
							children: L("manage:photoFilter.rebuildVector")
						}),
						/* @__PURE__ */ (0, W.jsx)(e, {
							size: "small",
							variant: "secondary",
							iconOnly: !0,
							leadingIcon: s,
							"aria-label": L("manage:photoFilter.deleteReference"),
							disabled: E.isPending,
							onClick: () => O(t)
						})
					]
				}, t.id))
			}) : /* @__PURE__ */ (0, W.jsx)(r, {
				size: "compact",
				icon: f,
				title: L("manage:photoFilter.noReferences"),
				children: L("manage:photoFilter.noReferencesHint")
			})
		]
	});
}
function ae({ onStarted: r, notify: o, settings: s }) {
	let [l, u] = (0, U.useState)(""), [d, f] = (0, U.useState)(String(t)), [p, m] = (0, U.useState)(String(n)), h = z({
		mutationFn: () => b({
			root_path: l.trim(),
			hit_threshold: Number(d),
			taste_threshold: Number(p)
		}),
		onSuccess: (e) => {
			r(e), o(L("manage:photoFilter.taskStarted"));
		}
	}), g = async () => {
		try {
			let e = await N(l);
			e && u(e);
		} catch (e) {
			o(T(e));
		}
	}, _ = s ? !s.model_ready : !1;
	return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.newTask"),
		children: [/* @__PURE__ */ (0, W.jsx)(Q, { title: L("manage:photoFilter.newTask") }), /* @__PURE__ */ (0, W.jsxs)("div", {
			className: "flex flex-col gap-3",
			children: [
				/* @__PURE__ */ (0, W.jsxs)("div", {
					className: "flex flex-wrap items-end gap-2",
					children: [/* @__PURE__ */ (0, W.jsx)(a, {
						label: L("manage:photoFilter.albumRoot"),
						value: l,
						onChange: u,
						placeholder: L("manage:photoFilter.albumRootPlaceholder"),
						className: "min-w-48 grow"
					}), /* @__PURE__ */ (0, W.jsx)(e, {
						size: "small",
						variant: "secondary",
						leadingIcon: V,
						onClick: () => void g(),
						children: L("manage:photoFilter.chooseFolder")
					})]
				}),
				/* @__PURE__ */ (0, W.jsxs)("div", {
					className: "flex flex-wrap items-end gap-2",
					children: [
						/* @__PURE__ */ (0, W.jsx)(a, {
							label: L("manage:photoFilter.hitThreshold"),
							type: "number",
							inputMode: "decimal",
							value: d,
							onChange: f,
							className: "w-36"
						}),
						/* @__PURE__ */ (0, W.jsx)(a, {
							label: L("manage:photoFilter.tasteThreshold"),
							type: "number",
							inputMode: "decimal",
							value: p,
							onChange: m,
							className: "w-36"
						}),
						/* @__PURE__ */ (0, W.jsx)(e, {
							size: "small",
							variant: "primary",
							leadingIcon: i,
							disabled: h.isPending || _ || !l.trim(),
							onClick: () => h.mutate(),
							children: L("manage:photoFilter.startFilter")
						})
					]
				}),
				/* @__PURE__ */ (0, W.jsx)("p", {
					className: K,
					children: L("manage:photoFilter.thresholdHint", {
						hit: t,
						taste: n
					})
				}),
				_ ? /* @__PURE__ */ (0, W.jsx)(c, {
					tone: "warning",
					children: L("manage:photoFilter.modelRequired")
				}) : null,
				h.error ? /* @__PURE__ */ (0, W.jsx)(c, {
					tone: "error",
					children: T(h.error)
				}) : null
			]
		})]
	});
}
function oe({ task: t, detail: n, loading: a, error: s, notify: l }) {
	let u = z({
		mutationFn: (e) => g(e),
		onSuccess: () => {
			P.invalidateQueries({ queryKey: d }), l(L("manage:photoFilter.taskCancelled"));
		}
	});
	if (a) return /* @__PURE__ */ (0, W.jsx)("section", {
		className: G,
		children: /* @__PURE__ */ (0, W.jsx)(p, {
			kind: "gather",
			label: L("manage:photoFilter.loadingResults")
		})
	});
	if (s) return /* @__PURE__ */ (0, W.jsx)("section", {
		className: G,
		children: /* @__PURE__ */ (0, W.jsx)(c, {
			tone: "error",
			children: T(s)
		})
	});
	if (!t || !n) return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.resultsTitle"),
		children: [/* @__PURE__ */ (0, W.jsx)(Q, { title: L("manage:photoFilter.resultsTitle") }), /* @__PURE__ */ (0, W.jsx)(r, {
			size: "compact",
			icon: i,
			title: L("manage:photoFilter.noTask"),
			children: L("manage:photoFilter.noTaskHint")
		})]
	});
	let f = n.results.filter((e) => e.tier !== "suspected" && e.tier !== "insufficient" && e.tier !== "failed"), m = n.results.filter((e) => e.tier === "suspected"), h = n.results.filter((e) => e.tier === "insufficient"), _ = n.results.filter((e) => e.tier === "failed");
	return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.resultsTitle"),
		children: [
			/* @__PURE__ */ (0, W.jsx)(Q, {
				title: L("manage:photoFilter.resultsTitle"),
				children: A(t) ? /* @__PURE__ */ (0, W.jsx)(e, {
					size: "small",
					variant: "secondary",
					leadingIcon: o,
					disabled: u.isPending,
					onClick: () => u.mutate(t.id),
					children: L("manage:photoFilter.cancel")
				}) : null
			}),
			/* @__PURE__ */ (0, W.jsx)("p", {
				className: K,
				children: L("manage:photoFilter.taskSummary", {
					root: t.root_path,
					status: X(t.status),
					done: t.processed_count,
					total: t.total_count
				})
			}),
			A(t) ? /* @__PURE__ */ (0, W.jsx)(p, {
				kind: "radar",
				label: L("manage:photoFilter.progress", {
					done: t.processed_count,
					total: t.total_count
				}),
				value: t.processed_count,
				total: t.total_count
			}) : null,
			t.status === "failed" ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "error",
				children: L("manage:photoFilter.taskFailed")
			}) : null,
			t.status === "cancelled" ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "warning",
				children: L("manage:photoFilter.taskWasCancelled")
			}) : null,
			u.error ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "error",
				children: T(u.error)
			}) : null,
			_.length ? /* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-2",
				children: [/* @__PURE__ */ (0, W.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: L("manage:photoFilter.zoneFailed")
				}), /* @__PURE__ */ (0, W.jsx)("ul", {
					className: "flex flex-col gap-1",
					children: _.map((e) => /* @__PURE__ */ (0, W.jsxs)("li", {
						className: "flex flex-wrap items-baseline gap-2 text-body-2-regular text-text-secondary",
						children: [/* @__PURE__ */ (0, W.jsx)("span", {
							className: "min-w-0 break-words text-text-primary",
							children: J(e)
						}), /* @__PURE__ */ (0, W.jsx)("span", { children: e.failure_reason || e.tier_label })]
					}, e.id))
				})]
			}) : null,
			f.length ? /* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [/* @__PURE__ */ (0, W.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: L("manage:photoFilter.zoneHits")
				}), /* @__PURE__ */ (0, W.jsx)("div", {
					className: "inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3",
					children: f.map((e) => /* @__PURE__ */ (0, W.jsx)($, {
						result: e,
						notify: l
					}, e.id))
				})]
			}) : n.results.length ? null : /* @__PURE__ */ (0, W.jsx)(r, {
				size: "compact",
				icon: i,
				title: L("manage:photoFilter.noResults"),
				children: L("manage:photoFilter.noResultsHint")
			}),
			m.length ? /* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [/* @__PURE__ */ (0, W.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: L("manage:photoFilter.zoneSuspected")
				}), /* @__PURE__ */ (0, W.jsx)("div", {
					className: "inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3",
					children: m.map((e) => /* @__PURE__ */ (0, W.jsx)($, {
						result: e,
						notify: l,
						suspected: !0
					}, e.id))
				})]
			}) : null,
			h.length ? /* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex flex-col gap-2",
				children: [/* @__PURE__ */ (0, W.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: L("manage:photoFilter.zoneInsufficient")
				}), /* @__PURE__ */ (0, W.jsx)("ul", {
					className: "flex flex-col gap-1",
					children: h.map((e) => /* @__PURE__ */ (0, W.jsxs)("li", {
						className: "flex flex-wrap items-baseline gap-2 text-body-2-regular text-text-secondary",
						children: [/* @__PURE__ */ (0, W.jsx)("span", {
							className: "min-w-0 break-words text-text-primary",
							children: J(e)
						}), /* @__PURE__ */ (0, W.jsx)("span", { children: L("manage:photoFilter.validImages", { count: e.valid_image_count }) })]
					}, e.id))
				})]
			}) : null
		]
	});
}
function $({ result: e, notify: t, suspected: n = !1 }) {
	let r = async () => {
		try {
			let n = await ne(e.id);
			t(n.mode === "server" && n.path ? L("manage:photoFilter.revealedServer", { path: n.path }) : L("manage:photoFilter.revealed"));
		} catch (e) {
			t(T(e));
		}
	};
	return /* @__PURE__ */ (0, W.jsxs)("button", {
		type: "button",
		onClick: () => void r(),
		className: "flex min-w-0 cursor-pointer flex-col gap-3 rounded-xl bg-background-primary-default p-3 text-left outline-none hover:bg-background-primary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring",
		children: [
			/* @__PURE__ */ (0, W.jsxs)("div", {
				className: "flex gap-3",
				children: [e.face_url ? /* @__PURE__ */ (0, W.jsx)("img", {
					src: e.face_url,
					alt: "",
					loading: "lazy",
					className: "size-16 shrink-0 rounded-lg bg-media-placeholder object-cover"
				}) : /* @__PURE__ */ (0, W.jsx)("span", { className: "size-16 shrink-0 rounded-lg bg-media-placeholder" }), /* @__PURE__ */ (0, W.jsxs)("span", {
					className: "flex min-w-0 flex-col gap-0.5",
					children: [
						/* @__PURE__ */ (0, W.jsx)("b", {
							className: "min-w-0 text-body-medium break-words text-text-primary",
							children: J(e)
						}),
						/* @__PURE__ */ (0, W.jsx)("small", {
							className: K,
							children: q[e.tier]
						}),
						/* @__PURE__ */ (0, W.jsx)("small", {
							className: K,
							children: L("manage:photoFilter.score", { score: e.score.toFixed(3) })
						})
					]
				})]
			}),
			n ? /* @__PURE__ */ (0, W.jsx)("span", {
				className: "rounded-lg bg-status-yellow-background px-2 py-1 text-caption-1-medium text-status-yellow-text",
				children: L("manage:photoFilter.suspectedMarker")
			}) : null,
			/* @__PURE__ */ (0, W.jsxs)("dl", {
				className: "inline-grid w-full grid-cols-2 gap-x-3 gap-y-1 text-caption-1-regular text-text-secondary",
				children: [
					/* @__PURE__ */ (0, W.jsx)("dt", { children: L("manage:photoFilter.topReference") }),
					/* @__PURE__ */ (0, W.jsx)("dd", {
						className: "min-w-0 truncate text-right text-text-primary",
						children: e.top_reference_name || L("manage:photoFilter.noReference")
					}),
					/* @__PURE__ */ (0, W.jsx)("dt", { children: L("manage:photoFilter.images") }),
					/* @__PURE__ */ (0, W.jsxs)("dd", {
						className: "text-right tabular-nums text-text-primary",
						children: [
							e.valid_image_count,
							" / ",
							e.total_image_count
						]
					}),
					/* @__PURE__ */ (0, W.jsx)("dt", { children: L("manage:photoFilter.protagonistShare") }),
					/* @__PURE__ */ (0, W.jsx)("dd", {
						className: "text-right tabular-nums text-text-primary",
						children: j(e.protagonist_cluster_ratio)
					})
				]
			}),
			e.protagonist_spread ? /* @__PURE__ */ (0, W.jsx)("span", {
				className: "text-caption-1-regular text-status-yellow-text",
				children: L("manage:photoFilter.protagonistSpread")
			}) : null
		]
	});
}
function se({ tasks: e, selected: t, error: n, onSelect: a, notify: o }) {
	return /* @__PURE__ */ (0, W.jsxs)("section", {
		className: G,
		"aria-label": L("manage:photoFilter.historyTitle"),
		children: [
			/* @__PURE__ */ (0, W.jsx)(Q, { title: L("manage:photoFilter.historyTitle") }),
			n ? /* @__PURE__ */ (0, W.jsx)(c, {
				tone: "error",
				children: T(n)
			}) : null,
			e.length ? /* @__PURE__ */ (0, W.jsx)("ul", {
				className: "flex flex-col gap-2",
				children: [...e].reverse().map((e) => /* @__PURE__ */ (0, W.jsx)("li", { children: /* @__PURE__ */ (0, W.jsxs)("button", {
					type: "button",
					onClick: () => {
						a(e.id), o(L("manage:photoFilter.historyOpened"));
					},
					"aria-current": e.id === t ? "true" : void 0,
					className: `flex w-full min-w-0 flex-col gap-1 rounded-xl p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring ${e.id === t ? "bg-background-primary-hover" : "bg-background-primary-default hover:bg-background-primary-hover"}`,
					children: [/* @__PURE__ */ (0, W.jsxs)("span", {
						className: "flex min-w-0 flex-wrap items-baseline gap-2",
						children: [/* @__PURE__ */ (0, W.jsx)("b", {
							className: "min-w-0 break-words text-body-2-medium text-text-primary",
							children: e.root_path
						}), /* @__PURE__ */ (0, W.jsx)("small", {
							className: K,
							children: X(e.status)
						})]
					}), /* @__PURE__ */ (0, W.jsx)("small", {
						className: K,
						children: L("manage:photoFilter.historySummary", {
							done: e.processed_count,
							total: e.total_count,
							count: e.result_count ?? 0
						})
					})]
				}) }, e.id))
			}) : /* @__PURE__ */ (0, W.jsx)(r, {
				size: "compact",
				icon: i,
				title: L("manage:photoFilter.noHistory"),
				children: L("manage:photoFilter.noHistoryHint")
			})
		]
	});
}
export { Z as PhotoFilterPage };

//# debugId=b445d6ba-b7dd-4a8c-a0be-500988ca5140