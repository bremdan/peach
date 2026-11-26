(function() {
	try {
		var e = typeof globalThis < "u" ? globalThis : typeof window < "u" ? window : typeof global < "u" ? global : typeof self < "u" ? self : {}, t = new e.Error().stack;
		t && (e._sentryDebugIds = e._sentryDebugIds || {}, e._sentryDebugIds[t] = "5527d0bc-c531-4768-b430-e9267290d21f", e._sentryDebugIdIdentifier = "sentry-dbid-5527d0bc-c531-4768-b430-e9267290d21f");
	} catch {}
})();
import { Button as e, DEFAULT_HIT_THRESHOLD as t, DEFAULT_TASTE_THRESHOLD as n, EmptyState as r, Gg as i, Input as a, LN as o, M6 as s, Note as c, PHOTO_FILTER_REFERENCES as l, PHOTO_FILTER_SETTINGS as u, PHOTO_FILTER_TASKS as d, Rf as f, TaskProgress as p, __toESM as m, albumName as h, cancelTask as g, cardClass as _, confirmModal as v, createReference as y, createTask as b, createUpload as x, dZ as ee, deleteReference as S, deleteUpload as C, errorMessage as w, fetchReferences as T, fetchSettings as E, fetchTask as D, fetchTasks as O, isRunning as k, percent as A, photoFilterTaskKey as j, pickAlbumRoot as M, queryClient as N, rebuildReference as P, require_jsx_runtime as F, require_react as I, revealResult as te, saveSettings as L, t as R, uploadPhoto as z, useMutation as B, useQuery as V, xs as H } from "./peach-app.js";
import { Page as U } from "./peach-app.page-QAncjzM1.js";
// src/react/photo-filter/photo-filter-page.tsx
var W = /* @__PURE__ */ m(I(), 1), G = F(), K = _(), q = "text-caption-1-regular text-text-secondary", J = {
	hit: R("manage:photoFilter.tierHit"),
	suspected: R("manage:photoFilter.tierSuspected"),
	taste: R("manage:photoFilter.tierTaste"),
	miss: R("manage:photoFilter.tierMiss"),
	insufficient: R("manage:photoFilter.tierInsufficient")
}, Y = {
	ready: R("manage:photoFilter.statusReady"),
	failed: R("manage:photoFilter.statusFailed"),
	pending: R("manage:photoFilter.statusPending"),
	running: R("manage:photoFilter.statusRunning"),
	completed: R("manage:photoFilter.statusCompleted"),
	cancelled: R("manage:photoFilter.statusCancelled")
}, X = (e) => Y[e] ?? e;
function Z({ toast: e }) {
	let t = V({
		queryKey: l,
		queryFn: ({ signal: e }) => T(e)
	}), n = V({
		queryKey: u,
		queryFn: ({ signal: e }) => E(e)
	}), r = V({
		queryKey: d,
		queryFn: ({ signal: e }) => O(e),
		refetchInterval: (e) => e.state.data?.tasks.some(k) ? 1500 : !1
	}), [i, a] = (0, W.useState)(null), o = r.data?.tasks ?? [], s = i ?? o[o.length - 1]?.id ?? null, c = V({
		queryKey: s ? j(s) : [
			"photo-filter",
			"task",
			"none"
		],
		queryFn: ({ signal: e }) => D(s, e),
		enabled: s != null,
		refetchInterval: (e) => k(e.state.data?.task) ? 1e3 : !1
	}), f = (t) => e?.(t);
	return /* @__PURE__ */ (0, G.jsxs)(U, { children: [
		/* @__PURE__ */ (0, G.jsx)(ne, {
			settings: n.data,
			error: n.error,
			notify: f
		}),
		/* @__PURE__ */ (0, G.jsx)(re, {
			references: t.data?.references ?? [],
			error: t.error,
			notify: f
		}),
		/* @__PURE__ */ (0, G.jsx)(ie, {
			onStarted: (e) => {
				a(e.id), N.invalidateQueries({ queryKey: d });
			},
			notify: f,
			settings: n.data
		}),
		/* @__PURE__ */ (0, G.jsx)(ae, {
			task: c.data?.task,
			detail: c.data,
			loading: c.isPending && s != null,
			error: c.error,
			notify: f
		}),
		/* @__PURE__ */ (0, G.jsx)(oe, {
			tasks: o,
			selected: s,
			error: r.error,
			onSelect: a,
			notify: f
		})
	] });
}
function Q({ title: e, children: t }) {
	return /* @__PURE__ */ (0, G.jsxs)("header", {
		className: "flex flex-wrap items-center justify-between gap-3",
		children: [/* @__PURE__ */ (0, G.jsx)("h3", {
			className: "text-title-2-medium text-text-primary",
			children: e
		}), t]
	});
}
function ne({ settings: t, error: n, notify: r }) {
	let [i, o] = (0, W.useState)("");
	(0, W.useEffect)(() => {
		t && o(t.model_root);
	}, [t?.model_root]);
	let s = B({
		mutationFn: () => L(i),
		onSuccess: () => {
			N.invalidateQueries({ queryKey: u }), r(R("manage:photoFilter.settingsSaved"));
		}
	}), l = async () => {
		try {
			let e = await M(i);
			e && o(e);
		} catch (e) {
			r(w(e));
		}
	};
	return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.settingsTitle"),
		children: [
			/* @__PURE__ */ (0, G.jsx)(Q, { title: R("manage:photoFilter.settingsTitle") }),
			n ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "error",
				children: w(n)
			}) : null,
			/* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex flex-col gap-2",
				children: [
					/* @__PURE__ */ (0, G.jsx)("span", {
						className: "text-body-2-medium text-text-primary",
						children: R("manage:photoFilter.modelDirectory")
					}),
					/* @__PURE__ */ (0, G.jsxs)("div", {
						className: "flex flex-wrap items-center gap-2",
						children: [
							/* @__PURE__ */ (0, G.jsx)(a, {
								"aria-label": R("manage:photoFilter.modelDirectory"),
								value: i,
								placeholder: R("manage:photoFilter.modelPlaceholder"),
								onChange: o,
								className: "min-w-48 grow"
							}),
							/* @__PURE__ */ (0, G.jsx)(e, {
								size: "small",
								variant: "secondary",
								leadingIcon: H,
								onClick: () => void l(),
								children: R("manage:photoFilter.chooseFolder")
							}),
							/* @__PURE__ */ (0, G.jsx)(e, {
								size: "small",
								variant: "primary",
								disabled: s.isPending,
								onClick: () => s.mutate(),
								children: R("manage:photoFilter.save")
							})
						]
					}),
					t ? t.model_ready ? /* @__PURE__ */ (0, G.jsx)("p", {
						className: q,
						children: R("manage:photoFilter.modelReady", { path: t.model_root_resolved })
					}) : /* @__PURE__ */ (0, G.jsx)(c, {
						tone: "warning",
						title: R("manage:photoFilter.modelMissingTitle"),
						children: R("manage:photoFilter.modelMissingHint", { path: t.model_root_resolved })
					}) : null,
					t && !t.runtime_available ? /* @__PURE__ */ (0, G.jsx)(c, {
						tone: "warning",
						children: R("manage:photoFilter.runtimeMissing")
					}) : null,
					t && t.runtime_available && !t.cuda_available ? /* @__PURE__ */ (0, G.jsx)(c, {
						tone: "info",
						children: R("manage:photoFilter.cpuFallback")
					}) : null,
					s.error ? /* @__PURE__ */ (0, G.jsx)(c, {
						tone: "error",
						children: w(s.error)
					}) : null
				]
			})
		]
	});
}
function re({ references: t, error: n, notify: i }) {
	let [o, u] = (0, W.useState)(""), [d, p] = (0, W.useState)([]), [m, h] = (0, W.useState)(""), g = (0, W.useRef)(null), _ = B({
		mutationFn: async () => {
			let e = d;
			if (e.length < 5 || e.length > 15) throw Error(R("manage:photoFilter.photoCount", {
				min: 5,
				max: 15
			}));
			let { token: t } = await x();
			try {
				for (let [n, r] of e.entries()) h(R("manage:photoFilter.uploading", {
					done: n + 1,
					total: e.length
				})), await z(t, r);
				return await y(o, t);
			} catch (e) {
				throw await C(t).catch(() => {}), e;
			} finally {
				h("");
			}
		},
		onSuccess: (e) => {
			u(""), p([]), g.current && (g.current.value = ""), N.invalidateQueries({ queryKey: l }), i(e.status === "ready" ? R("manage:photoFilter.referenceCreated", { count: e.valid_face_count }) : R("manage:photoFilter.insufficientFaces", {
				count: e.valid_face_count,
				needed: 3
			}));
		}
	}), b = B({
		mutationFn: (e) => P(e),
		onSuccess: () => void N.invalidateQueries({ queryKey: l })
	}), T = B({
		mutationFn: (e) => S(e),
		onSuccess: () => void N.invalidateQueries({ queryKey: l })
	}), E = (e) => p(e.slice(0, 20)), D = (e) => {
		v({
			title: R("manage:photoFilter.deleteReference"),
			body: R("manage:photoFilter.deleteReferenceBody", { name: e.name }),
			confirmLabel: R("manage:photoFilter.deleteReference"),
			holdToConfirm: !0,
			onConfirm: () => T.mutateAsync(e.id)
		});
	};
	return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.referencesTitle"),
		children: [
			/* @__PURE__ */ (0, G.jsx)(Q, { title: R("manage:photoFilter.referencesTitle") }),
			/* @__PURE__ */ (0, G.jsx)(c, {
				tone: "info",
				children: R("manage:photoFilter.sameDomainHint")
			}),
			n ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "error",
				children: w(n)
			}) : null,
			/* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [
					/* @__PURE__ */ (0, G.jsx)("span", {
						className: "text-body-2-medium text-text-primary",
						children: R("manage:photoFilter.newReference")
					}),
					/* @__PURE__ */ (0, G.jsxs)("div", {
						className: "flex flex-wrap items-end gap-2",
						children: [
							/* @__PURE__ */ (0, G.jsx)(a, {
								label: R("manage:photoFilter.name"),
								value: o,
								onChange: u,
								className: "min-w-40 grow"
							}),
							/* @__PURE__ */ (0, G.jsx)("input", {
								ref: g,
								type: "file",
								multiple: !0,
								accept: "image/jpeg,image/png,image/webp,image/bmp",
								tabIndex: -1,
								"aria-hidden": !0,
								className: "hidden",
								onChange: (e) => E(Array.from(e.currentTarget.files ?? []))
							}),
							/* @__PURE__ */ (0, G.jsx)(e, {
								size: "small",
								variant: "secondary",
								leadingIcon: f,
								onClick: () => g.current?.click(),
								children: R("manage:photoFilter.choosePhotos")
							}),
							/* @__PURE__ */ (0, G.jsx)(e, {
								size: "small",
								variant: "primary",
								disabled: _.isPending || !o.trim() || !d.length,
								onClick: () => _.mutate(),
								children: R("manage:photoFilter.buildVector")
							})
						]
					}),
					/* @__PURE__ */ (0, G.jsx)("p", {
						className: q,
						children: R("manage:photoFilter.photoCountHint", {
							min: 5,
							max: 15,
							count: d.length
						})
					}),
					m ? /* @__PURE__ */ (0, G.jsx)("p", {
						className: q,
						children: m
					}) : null,
					_.error ? /* @__PURE__ */ (0, G.jsx)(c, {
						tone: "error",
						children: w(_.error)
					}) : null
				]
			}),
			t.length ? /* @__PURE__ */ (0, G.jsx)("ul", {
				className: "flex flex-col gap-2",
				children: t.map((t) => /* @__PURE__ */ (0, G.jsxs)("li", {
					className: "flex flex-wrap items-center gap-3 rounded-xl bg-background-primary-default p-3",
					children: [
						/* @__PURE__ */ (0, G.jsxs)("span", {
							className: "flex min-w-0 grow flex-col gap-0.5",
							children: [/* @__PURE__ */ (0, G.jsx)("b", {
								className: "min-w-0 text-body-medium break-words text-text-primary",
								children: t.name
							}), /* @__PURE__ */ (0, G.jsxs)("small", {
								className: q,
								children: [
									R("manage:photoFilter.validFaces", { count: t.valid_face_count }),
									" · ",
									X(t.status),
									t.status === "failed" ? ` · ${R("manage:photoFilter.addMorePhotos", { needed: 3 })}` : ""
								]
							})]
						}),
						/* @__PURE__ */ (0, G.jsx)(e, {
							size: "small",
							variant: "secondary",
							leadingIcon: ee,
							disabled: b.isPending,
							onClick: () => b.mutate(t.id),
							children: R("manage:photoFilter.rebuildVector")
						}),
						/* @__PURE__ */ (0, G.jsx)(e, {
							size: "small",
							variant: "secondary",
							iconOnly: !0,
							leadingIcon: s,
							"aria-label": R("manage:photoFilter.deleteReference"),
							disabled: T.isPending,
							onClick: () => D(t)
						})
					]
				}, t.id))
			}) : /* @__PURE__ */ (0, G.jsx)(r, {
				size: "compact",
				icon: f,
				title: R("manage:photoFilter.noReferences"),
				children: R("manage:photoFilter.noReferencesHint")
			})
		]
	});
}
function ie({ onStarted: r, notify: o, settings: s }) {
	let [l, u] = (0, W.useState)(""), [d, f] = (0, W.useState)(String(t)), [p, m] = (0, W.useState)(String(n)), h = B({
		mutationFn: () => b({
			root_path: l.trim(),
			hit_threshold: Number(d),
			taste_threshold: Number(p)
		}),
		onSuccess: (e) => {
			r(e), o(R("manage:photoFilter.taskStarted"));
		}
	}), g = async () => {
		try {
			let e = await M(l);
			e && u(e);
		} catch (e) {
			o(w(e));
		}
	}, _ = s ? !s.model_ready : !1;
	return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.newTask"),
		children: [/* @__PURE__ */ (0, G.jsx)(Q, { title: R("manage:photoFilter.newTask") }), /* @__PURE__ */ (0, G.jsxs)("div", {
			className: "flex flex-col gap-3",
			children: [
				/* @__PURE__ */ (0, G.jsxs)("div", {
					className: "flex flex-wrap items-end gap-2",
					children: [/* @__PURE__ */ (0, G.jsx)(a, {
						label: R("manage:photoFilter.albumRoot"),
						value: l,
						onChange: u,
						placeholder: R("manage:photoFilter.albumRootPlaceholder"),
						className: "min-w-48 grow"
					}), /* @__PURE__ */ (0, G.jsx)(e, {
						size: "small",
						variant: "secondary",
						leadingIcon: H,
						onClick: () => void g(),
						children: R("manage:photoFilter.chooseFolder")
					})]
				}),
				/* @__PURE__ */ (0, G.jsxs)("div", {
					className: "flex flex-wrap items-end gap-2",
					children: [
						/* @__PURE__ */ (0, G.jsx)(a, {
							label: R("manage:photoFilter.hitThreshold"),
							type: "number",
							inputMode: "decimal",
							value: d,
							onChange: f,
							className: "w-36"
						}),
						/* @__PURE__ */ (0, G.jsx)(a, {
							label: R("manage:photoFilter.tasteThreshold"),
							type: "number",
							inputMode: "decimal",
							value: p,
							onChange: m,
							className: "w-36"
						}),
						/* @__PURE__ */ (0, G.jsx)(e, {
							size: "small",
							variant: "primary",
							leadingIcon: i,
							disabled: h.isPending || _ || !l.trim(),
							onClick: () => h.mutate(),
							children: R("manage:photoFilter.startFilter")
						})
					]
				}),
				/* @__PURE__ */ (0, G.jsx)("p", {
					className: q,
					children: R("manage:photoFilter.thresholdHint", {
						hit: t,
						taste: n
					})
				}),
				_ ? /* @__PURE__ */ (0, G.jsx)(c, {
					tone: "warning",
					children: R("manage:photoFilter.modelRequired")
				}) : null,
				h.error ? /* @__PURE__ */ (0, G.jsx)(c, {
					tone: "error",
					children: w(h.error)
				}) : null
			]
		})]
	});
}
function ae({ task: t, detail: n, loading: a, error: s, notify: l }) {
	let u = B({
		mutationFn: (e) => g(e),
		onSuccess: () => {
			N.invalidateQueries({ queryKey: d }), l(R("manage:photoFilter.taskCancelled"));
		}
	});
	if (a) return /* @__PURE__ */ (0, G.jsx)("section", {
		className: K,
		children: /* @__PURE__ */ (0, G.jsx)(p, {
			kind: "gather",
			label: R("manage:photoFilter.loadingResults")
		})
	});
	if (s) return /* @__PURE__ */ (0, G.jsx)("section", {
		className: K,
		children: /* @__PURE__ */ (0, G.jsx)(c, {
			tone: "error",
			children: w(s)
		})
	});
	if (!t || !n) return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.resultsTitle"),
		children: [/* @__PURE__ */ (0, G.jsx)(Q, { title: R("manage:photoFilter.resultsTitle") }), /* @__PURE__ */ (0, G.jsx)(r, {
			size: "compact",
			icon: i,
			title: R("manage:photoFilter.noTask"),
			children: R("manage:photoFilter.noTaskHint")
		})]
	});
	let f = n.results.filter((e) => e.tier !== "suspected" && e.tier !== "insufficient"), m = n.results.filter((e) => e.tier === "suspected"), _ = n.results.filter((e) => e.tier === "insufficient");
	return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.resultsTitle"),
		children: [
			/* @__PURE__ */ (0, G.jsx)(Q, {
				title: R("manage:photoFilter.resultsTitle"),
				children: k(t) ? /* @__PURE__ */ (0, G.jsx)(e, {
					size: "small",
					variant: "secondary",
					leadingIcon: o,
					disabled: u.isPending,
					onClick: () => u.mutate(t.id),
					children: R("manage:photoFilter.cancel")
				}) : null
			}),
			/* @__PURE__ */ (0, G.jsx)("p", {
				className: q,
				children: R("manage:photoFilter.taskSummary", {
					root: t.root_path,
					status: X(t.status),
					done: t.processed_count,
					total: t.total_count
				})
			}),
			k(t) ? /* @__PURE__ */ (0, G.jsx)(p, {
				kind: "radar",
				label: R("manage:photoFilter.progress", {
					done: t.processed_count,
					total: t.total_count
				}),
				value: t.processed_count,
				total: t.total_count
			}) : null,
			t.status === "failed" ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "error",
				children: R("manage:photoFilter.taskFailed")
			}) : null,
			t.status === "cancelled" ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "warning",
				children: R("manage:photoFilter.taskWasCancelled")
			}) : null,
			u.error ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "error",
				children: w(u.error)
			}) : null,
			f.length ? /* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [/* @__PURE__ */ (0, G.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: R("manage:photoFilter.zoneHits")
				}), /* @__PURE__ */ (0, G.jsx)("div", {
					className: "inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3",
					children: f.map((e) => /* @__PURE__ */ (0, G.jsx)($, {
						result: e,
						notify: l
					}, e.id))
				})]
			}) : n.results.length ? null : /* @__PURE__ */ (0, G.jsx)(r, {
				size: "compact",
				icon: i,
				title: R("manage:photoFilter.noResults"),
				children: R("manage:photoFilter.noResultsHint")
			}),
			m.length ? /* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex flex-col gap-3",
				children: [/* @__PURE__ */ (0, G.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: R("manage:photoFilter.zoneSuspected")
				}), /* @__PURE__ */ (0, G.jsx)("div", {
					className: "inline-grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3",
					children: m.map((e) => /* @__PURE__ */ (0, G.jsx)($, {
						result: e,
						notify: l,
						suspected: !0
					}, e.id))
				})]
			}) : null,
			_.length ? /* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex flex-col gap-2",
				children: [/* @__PURE__ */ (0, G.jsx)("h4", {
					className: "text-body-semibold text-text-primary",
					children: R("manage:photoFilter.zoneInsufficient")
				}), /* @__PURE__ */ (0, G.jsx)("ul", {
					className: "flex flex-col gap-1",
					children: _.map((e) => /* @__PURE__ */ (0, G.jsxs)("li", {
						className: "flex flex-wrap items-baseline gap-2 text-body-2-regular text-text-secondary",
						children: [/* @__PURE__ */ (0, G.jsx)("span", {
							className: "min-w-0 break-words text-text-primary",
							children: h(e.album_path)
						}), /* @__PURE__ */ (0, G.jsx)("span", { children: R("manage:photoFilter.validImages", { count: e.valid_image_count }) })]
					}, e.id))
				})]
			}) : null
		]
	});
}
function $({ result: e, notify: t, suspected: n = !1 }) {
	let r = async () => {
		try {
			let n = await te(e.id);
			t(n.mode === "server" && n.path ? R("manage:photoFilter.revealedServer", { path: n.path }) : R("manage:photoFilter.revealed"));
		} catch (e) {
			t(w(e));
		}
	};
	return /* @__PURE__ */ (0, G.jsxs)("button", {
		type: "button",
		onClick: () => void r(),
		className: "flex min-w-0 cursor-pointer flex-col gap-3 rounded-xl bg-background-primary-default p-3 text-left outline-none hover:bg-background-primary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring",
		children: [
			/* @__PURE__ */ (0, G.jsxs)("div", {
				className: "flex gap-3",
				children: [e.face_url ? /* @__PURE__ */ (0, G.jsx)("img", {
					src: e.face_url,
					alt: "",
					loading: "lazy",
					className: "size-16 shrink-0 rounded-lg bg-media-placeholder object-cover"
				}) : /* @__PURE__ */ (0, G.jsx)("span", { className: "size-16 shrink-0 rounded-lg bg-media-placeholder" }), /* @__PURE__ */ (0, G.jsxs)("span", {
					className: "flex min-w-0 flex-col gap-0.5",
					children: [
						/* @__PURE__ */ (0, G.jsx)("b", {
							className: "min-w-0 text-body-medium break-words text-text-primary",
							children: h(e.album_path)
						}),
						/* @__PURE__ */ (0, G.jsx)("small", {
							className: q,
							children: J[e.tier]
						}),
						/* @__PURE__ */ (0, G.jsx)("small", {
							className: q,
							children: R("manage:photoFilter.score", { score: e.score.toFixed(3) })
						})
					]
				})]
			}),
			n ? /* @__PURE__ */ (0, G.jsx)("span", {
				className: "rounded-lg bg-status-yellow-background px-2 py-1 text-caption-1-medium text-status-yellow-text",
				children: R("manage:photoFilter.suspectedMarker")
			}) : null,
			/* @__PURE__ */ (0, G.jsxs)("dl", {
				className: "inline-grid w-full grid-cols-2 gap-x-3 gap-y-1 text-caption-1-regular text-text-secondary",
				children: [
					/* @__PURE__ */ (0, G.jsx)("dt", { children: R("manage:photoFilter.topReference") }),
					/* @__PURE__ */ (0, G.jsx)("dd", {
						className: "min-w-0 truncate text-right text-text-primary",
						children: e.top_reference_name || R("manage:photoFilter.noReference")
					}),
					/* @__PURE__ */ (0, G.jsx)("dt", { children: R("manage:photoFilter.images") }),
					/* @__PURE__ */ (0, G.jsxs)("dd", {
						className: "text-right tabular-nums text-text-primary",
						children: [
							e.valid_image_count,
							" / ",
							e.total_image_count
						]
					}),
					/* @__PURE__ */ (0, G.jsx)("dt", { children: R("manage:photoFilter.protagonistShare") }),
					/* @__PURE__ */ (0, G.jsx)("dd", {
						className: "text-right tabular-nums text-text-primary",
						children: A(e.protagonist_cluster_ratio)
					})
				]
			}),
			e.protagonist_spread ? /* @__PURE__ */ (0, G.jsx)("span", {
				className: "text-caption-1-regular text-status-yellow-text",
				children: R("manage:photoFilter.protagonistSpread")
			}) : null
		]
	});
}
function oe({ tasks: e, selected: t, error: n, onSelect: a, notify: o }) {
	return /* @__PURE__ */ (0, G.jsxs)("section", {
		className: K,
		"aria-label": R("manage:photoFilter.historyTitle"),
		children: [
			/* @__PURE__ */ (0, G.jsx)(Q, { title: R("manage:photoFilter.historyTitle") }),
			n ? /* @__PURE__ */ (0, G.jsx)(c, {
				tone: "error",
				children: w(n)
			}) : null,
			e.length ? /* @__PURE__ */ (0, G.jsx)("ul", {
				className: "flex flex-col gap-2",
				children: [...e].reverse().map((e) => /* @__PURE__ */ (0, G.jsx)("li", { children: /* @__PURE__ */ (0, G.jsxs)("button", {
					type: "button",
					onClick: () => {
						a(e.id), o(R("manage:photoFilter.historyOpened"));
					},
					"aria-current": e.id === t ? "true" : void 0,
					className: `flex w-full min-w-0 flex-col gap-1 rounded-xl p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring ${e.id === t ? "bg-background-primary-hover" : "bg-background-primary-default hover:bg-background-primary-hover"}`,
					children: [/* @__PURE__ */ (0, G.jsxs)("span", {
						className: "flex min-w-0 flex-wrap items-baseline gap-2",
						children: [/* @__PURE__ */ (0, G.jsx)("b", {
							className: "min-w-0 break-words text-body-2-medium text-text-primary",
							children: e.root_path
						}), /* @__PURE__ */ (0, G.jsx)("small", {
							className: q,
							children: X(e.status)
						})]
					}), /* @__PURE__ */ (0, G.jsx)("small", {
						className: q,
						children: R("manage:photoFilter.historySummary", {
							done: e.processed_count,
							total: e.total_count,
							count: e.result_count ?? 0
						})
					})]
				}) }, e.id))
			}) : /* @__PURE__ */ (0, G.jsx)(r, {
				size: "compact",
				icon: i,
				title: R("manage:photoFilter.noHistory"),
				children: R("manage:photoFilter.noHistoryHint")
			})
		]
	});
}
export { Z as PhotoFilterPage };

//# debugId=5527d0bc-c531-4768-b430-e9267290d21f