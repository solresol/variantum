(function () {
    const VISIBILITY_THRESHOLD = 0.25;

    function setStatus(message) {
        const status = document.querySelector("[data-form-status]");
        if (status) {
            status.textContent = message || "";
        }
    }

    function applyRating(variantID, rating) {
        const radio = document.querySelector(`[name="${CSS.escape(`rating_${variantID}`)}"][value="${rating}"]`);
        if (radio) {
            radio.checked = true;
        }
    }

    function applyState(state) {
        if (!state || !state.ratings) {
            return;
        }
        for (const [variantID, rating] of Object.entries(state.ratings)) {
            if (rating.rating !== null && rating.rating !== undefined) {
                applyRating(variantID, rating.rating);
            }
        }
    }

    async function loadState() {
        const body = document.body;
        const packSlug = body.dataset.packSlug;
        const passageID = body.dataset.passageId;
        if (!packSlug || !passageID) {
            return;
        }
        const params = new URLSearchParams({ pack_slug: packSlug, passage_id: passageID });
        const response = await fetch(`/cgi-bin/review-state.cgi?${params}`, { credentials: "same-origin" });
        if (!response.ok) {
            throw new Error(`state request failed: ${response.status}`);
        }
        applyState(await response.json());
    }

    function formPayload(form) {
        return new URLSearchParams(new FormData(form));
    }

    async function postForm(form, payload) {
        const response = await fetch(form.action, {
            method: "POST",
            body: payload,
            credentials: "same-origin",
            keepalive: true,
            redirect: "manual",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
        });
        if (!response.ok && response.status !== 303 && response.type !== "opaqueredirect") {
            throw new Error(`save request failed: ${response.status}`);
        }
    }

    function setupHelperVisibility() {
        const body = document.body;
        const helperRegion = document.querySelector("[data-helper-region]");
        const focalCard = document.querySelector(".focal-card");
        if (!helperRegion) {
            return;
        }
        body.classList.add("js-enabled");
        const revealKeys = new Set(["ArrowDown", "PageDown", " ", "Spacebar", "End"]);

        function revealHelpers() {
            if (!body.classList.contains("helpers-visible")) {
                body.classList.add("helpers-visible");
                window.dispatchEvent(new CustomEvent("helpers-visible"));
            }
        }

        function revealOnIntent(event) {
            if (event.type === "keydown" && !revealKeys.has(event.key)) {
                return;
            }
            revealHelpers();
        }

        if (window.scrollY > 8) {
            revealHelpers();
            return;
        }
        window.addEventListener(
            "scroll",
            () => {
                if (window.scrollY > 8) {
                    revealHelpers();
                }
            },
            { passive: true, once: true },
        );
        document.addEventListener("wheel", revealOnIntent, { passive: true, capture: true });
        document.addEventListener("touchmove", revealOnIntent, { passive: true, capture: true });
        document.addEventListener("keydown", revealOnIntent, { capture: true });
        if (focalCard) {
            focalCard.addEventListener("scroll", revealHelpers, { passive: true, once: true });
        }
    }

    function setupExposureTracking() {
        const exposureInput = document.querySelector("[data-exposure-json]");
        const helperCards = Array.from(document.querySelectorAll(".helper-card[data-variant-id]"));
        const focalCard = document.querySelector(".focal-card");
        const form = document.querySelector("[data-review-form]");
        if (!exposureInput || helperCards.length === 0) {
            return;
        }

        const ratios = new Map();
        const activeSince = new Map();
        const exposure = new Map();
        let helpersVisible = document.body.classList.contains("helpers-visible");
        let measureQueued = false;

        function timestamp() {
            return performance.now();
        }

        function ensureExposure(variantID) {
            if (!exposure.has(variantID)) {
                exposure.set(variantID, {
                    visibleMs: 0,
                    firstVisibleMs: null,
                    lastVisibleMs: null,
                    viewCount: 0,
                    maxRatio: 0,
                });
            }
            return exposure.get(variantID);
        }

        function startVisible(variantID, ratio) {
            const now = timestamp();
            const row = ensureExposure(variantID);
            row.maxRatio = Math.max(row.maxRatio, ratio);
            if (activeSince.has(variantID)) {
                return;
            }
            activeSince.set(variantID, now);
            row.viewCount += 1;
            if (row.firstVisibleMs === null) {
                row.firstVisibleMs = now;
            }
        }

        function stopVisible(variantID) {
            if (!activeSince.has(variantID)) {
                return;
            }
            const now = timestamp();
            const started = activeSince.get(variantID);
            const row = ensureExposure(variantID);
            row.visibleMs += Math.max(0, now - started);
            row.lastVisibleMs = now;
            activeSince.delete(variantID);
        }

        function reconcileVisibility() {
            for (const card of helperCards) {
                const variantID = card.dataset.variantId;
                const ratio = ratios.get(variantID) || 0;
                if (helpersVisible && !document.hidden && ratio >= VISIBILITY_THRESHOLD) {
                    startVisible(variantID, ratio);
                } else {
                    stopVisible(variantID);
                }
            }
        }

        function occlusionBottom() {
            if (!helpersVisible || !focalCard) {
                return 0;
            }
            const rect = focalCard.getBoundingClientRect();
            if (rect.bottom <= 0 || rect.top >= window.innerHeight) {
                return 0;
            }
            return Math.min(window.innerHeight, Math.max(0, rect.bottom + 8));
        }

        function measureRatios() {
            const hiddenTop = occlusionBottom();
            for (const card of helperCards) {
                const variantID = card.dataset.variantId;
                const rect = card.getBoundingClientRect();
                const visibleTop = Math.max(rect.top, hiddenTop, 0);
                const visibleBottom = Math.min(rect.bottom, window.innerHeight);
                const visibleHeight = Math.max(0, visibleBottom - visibleTop);
                const ratio = rect.height > 0 ? Math.max(0, Math.min(1, visibleHeight / rect.height)) : 0;
                ratios.set(variantID, ratio);
                ensureExposure(variantID).maxRatio = Math.max(ensureExposure(variantID).maxRatio, ratio);
            }
        }

        function updateVisibility() {
            measureRatios();
            reconcileVisibility();
        }

        function scheduleVisibilityUpdate() {
            if (measureQueued) {
                return;
            }
            measureQueued = true;
            requestAnimationFrame(() => {
                measureQueued = false;
                updateVisibility();
            });
        }

        function snapshotExposure() {
            updateVisibility();
            const now = timestamp();
            const variants = {};
            for (const [variantID, row] of exposure.entries()) {
                const activeDelta = activeSince.has(variantID) ? Math.max(0, now - activeSince.get(variantID)) : 0;
                variants[variantID] = {
                    visible_ms: Math.round(row.visibleMs + activeDelta),
                    first_visible_ms: row.firstVisibleMs === null ? null : Math.round(row.firstVisibleMs),
                    last_visible_ms: activeSince.has(variantID)
                        ? Math.round(now)
                        : row.lastVisibleMs === null
                          ? null
                          : Math.round(row.lastVisibleMs),
                    view_count: row.viewCount,
                    max_intersection_ratio: Number(row.maxRatio.toFixed(3)),
                };
            }
            exposureInput.value = JSON.stringify({
                schema_version: 1,
                page_loaded_at: new Date(performance.timeOrigin).toISOString(),
                captured_at_ms: Math.round(timestamp()),
                helper_visibility_threshold: VISIBILITY_THRESHOLD,
                helpers_revealed: helpersVisible,
                variants,
            });
        }

        function resetExposureClocks() {
            activeSince.clear();
            exposure.clear();
            ratios.clear();
            for (const card of helperCards) {
                ratios.set(card.dataset.variantId, 0);
            }
            updateVisibility();
            snapshotExposure();
        }

        for (const card of helperCards) {
            ratios.set(card.dataset.variantId, 0);
        }

        window.addEventListener("helpers-visible", () => {
            helpersVisible = true;
            updateVisibility();
            snapshotExposure();
        });
        window.addEventListener("scroll", scheduleVisibilityUpdate, { passive: true });
        window.addEventListener("resize", scheduleVisibilityUpdate);
        document.addEventListener("visibilitychange", snapshotExposure);
        window.addEventListener("pagehide", snapshotExposure);
        window.addEventListener("beforeunload", snapshotExposure);
        if (form) {
            form.addEventListener("submit", snapshotExposure);
        }
        window.variantumReview = window.variantumReview || {};
        window.variantumReview.snapshotExposure = snapshotExposure;
        window.variantumReview.resetExposureClocks = resetExposureClocks;
        snapshotExposure();
    }

    function setupRatingAutosave() {
        const form = document.querySelector("[data-review-form]");
        if (!form) {
            return;
        }
        const ratingInputs = Array.from(form.querySelectorAll('.rating-grid-11 input[type="radio"]'));
        if (ratingInputs.length === 0) {
            return;
        }

        let saveQueue = Promise.resolve();
        let lastClickAt = 0;

        function snapshotAndReset() {
            if (window.variantumReview && typeof window.variantumReview.snapshotExposure === "function") {
                window.variantumReview.snapshotExposure();
            }
            const payload = formPayload(form);
            if (window.variantumReview && typeof window.variantumReview.resetExposureClocks === "function") {
                window.variantumReview.resetExposureClocks();
            }
            return payload;
        }

        function queueSave(payload) {
            setStatus("Saving...");
            saveQueue = saveQueue
                .catch(() => undefined)
                .then(() => postForm(form, payload))
                .then(() => {
                    setStatus("Saved.");
                })
                .catch(() => {
                    setStatus("Save failed. Try again before leaving this page.");
                });
        }

        function saveCurrentRating() {
            queueSave(snapshotAndReset());
        }

        for (const input of ratingInputs) {
            input.addEventListener("click", () => {
                lastClickAt = performance.now();
                saveCurrentRating();
            });
            input.addEventListener("change", () => {
                if (performance.now() - lastClickAt > 120) {
                    saveCurrentRating();
                }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const params = new URLSearchParams(window.location.search);
        if (params.has("saved")) {
            setStatus("Saved.");
        }
        setupHelperVisibility();
        setupExposureTracking();
        setupRatingAutosave();
        loadState().catch(() => {
            setStatus("Saved ratings could not be loaded.");
        });
    });
})();
