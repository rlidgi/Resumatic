import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
    DndContext,
    PointerSensor,
    KeyboardSensor,
    closestCenter,
    pointerWithin,
    rectIntersection,
    MeasuringStrategy,
    type DragCancelEvent,
    type DragEndEvent,
    type DragStartEvent,
    useSensor,
    useSensors,
    useDroppable,
} from '@dnd-kit/core';
import {
    SortableContext,
    verticalListSortingStrategy,
    arrayMove,
    sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { EditableSection } from './EditableSection';

export type SortableSectionRow = {
    key: string;
    title?: string;
    content: React.ReactNode;
};

const TRASH_DROP_ID = '__trash_drop_zone__';

function orderRows(rows: SortableSectionRow[], sectionOrder: string[], hiddenSectionKeys: string[]): SortableSectionRow[] {
    const hidden = new Set((Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : []).map(String));
    const visibleRows = rows.filter((r) => !hidden.has(r.key));

    if (!Array.isArray(sectionOrder) || sectionOrder.length === 0) return visibleRows;

    const rowByKey = new Map(visibleRows.map((r) => [r.key, r] as const));
    const ordered: SortableSectionRow[] = [];

    for (const key of sectionOrder) {
        const row = rowByKey.get(key);
        if (row) ordered.push(row);
    }

    for (const row of visibleRows) {
        if (!sectionOrder.includes(row.key)) ordered.push(row);
    }

    return ordered;
}

export default function SortableSectionList({
    rows,
    editMode,
    sectionOrder,
    onSectionOrderChange,
    hiddenSectionKeys,
    onHiddenSectionKeysChange,
}: {
    rows: SortableSectionRow[];
    editMode: boolean;
    sectionOrder?: string[];
    onSectionOrderChange?: (order: string[]) => void;
    hiddenSectionKeys?: string[];
    onHiddenSectionKeysChange?: (keys: string[]) => void;
}) {
    const safeOrder = Array.isArray(sectionOrder) ? sectionOrder : [];
    const safeHidden = Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : [];

    const orderedRows = useMemo(() => {
        return orderRows(rows, safeOrder, safeHidden);
    }, [rows, safeOrder, safeHidden]);

    const orderedKeys = useMemo(() => orderedRows.map((r) => r.key), [orderedRows]);

    // IMPORTANT: do not initialize dnd-kit sensors/hooks unless we are actually in edit mode.
    // In view-only mode, some environments/bundles can throw runtime TDZ errors when these hooks run.
    if (!editMode || !onSectionOrderChange) {
        return (
            <>
                {orderedRows.map((row) => (
                    <React.Fragment key={row.key}>{row.content}</React.Fragment>
                ))}
            </>
        );
    }

    return (
        <SortableSectionListDnd
            editMode={editMode}
            orderedRows={orderedRows}
            orderedKeys={orderedKeys}
            rows={rows}
            safeOrder={safeOrder}
            onSectionOrderChange={onSectionOrderChange}
            hiddenSectionKeys={safeHidden}
            onHiddenSectionKeysChange={onHiddenSectionKeysChange}
        />
    );
}

function SortableSectionListDnd({
    editMode,
    orderedRows,
    orderedKeys,
    rows,
    safeOrder,
    onSectionOrderChange,
    hiddenSectionKeys,
    onHiddenSectionKeysChange,
}: {
    editMode: boolean;
    orderedRows: SortableSectionRow[];
    orderedKeys: string[];
    rows: SortableSectionRow[];
    safeOrder: string[];
    onSectionOrderChange: (order: string[]) => void;
    hiddenSectionKeys: string[];
    onHiddenSectionKeysChange?: (keys: string[]) => void;
}) {
    const safeHidden = Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : [];
    const hiddenSet = useMemo(() => new Set(safeHidden.map(String)), [safeHidden]);

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: { distance: 6 },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const [activeKey, setActiveKey] = useState<string | null>(null);
    const [manualTrashHover, setManualTrashHover] = useState(false);
    const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
    const trashElRef = useRef<HTMLDivElement | null>(null);
    const [canUseDom, setCanUseDom] = useState(false);
    const undoTimerRef = useRef<number | null>(null);
    const [undoState, setUndoState] = useState<null | {
        prevOrder: string[];
        prevHidden: string[];
    }>(null);

    useEffect(() => {
        setCanUseDom(true);
        return () => {
            if (undoTimerRef.current) {
                window.clearTimeout(undoTimerRef.current);
                undoTimerRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (!editMode) return;
        if (safeOrder.length > 0) return;
        if (rows.length === 0) return;
        onSectionOrderChange(rows.filter((r) => !hiddenSet.has(r.key)).map((r) => r.key));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [editMode, onSectionOrderChange, rows.length]);

    useEffect(() => {
        if (!editMode) return;
        if (safeOrder.length === 0) return;

        const missing = rows
            .filter((r) => !hiddenSet.has(r.key))
            .map((r) => r.key)
            .filter((k) => !safeOrder.includes(k));
        if (missing.length === 0) return;
        onSectionOrderChange([...safeOrder, ...missing]);
    }, [editMode, onSectionOrderChange, rows, safeOrder, hiddenSet]);

    const setHiddenKeys = useCallback((next: string[]) => {
        if (onHiddenSectionKeysChange) onHiddenSectionKeysChange(next);
    }, [onHiddenSectionKeysChange]);

    const showUndo = useCallback((prevOrder: string[], prevHidden: string[]) => {
        setUndoState({ prevOrder, prevHidden });
        if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);
        undoTimerRef.current = window.setTimeout(() => {
            setUndoState(null);
            undoTimerRef.current = null;
        }, 6000);
    }, []);

    const removeSectionKey = useCallback((key: string) => {
        const prevOrder = [...orderedKeys];
        const prevHidden = [...safeHidden];

        const nextHidden = Array.from(new Set([...safeHidden, String(key)]));
        const nextOrder = orderedKeys.filter((k) => k !== key);

        setHiddenKeys(nextHidden);
        onSectionOrderChange(nextOrder);
        showUndo(prevOrder, prevHidden);
    }, [onSectionOrderChange, orderedKeys, safeHidden, setHiddenKeys, showUndo]);

    const isPointerInTrash = useCallback(() => {
        const p = lastPointerRef.current;
        const el = trashElRef.current;
        if (!p || !el) return false;
        const rect = el.getBoundingClientRect();
        return p.x >= rect.left && p.x <= rect.right && p.y >= rect.top && p.y <= rect.bottom;
    }, []);

    const onPointerMove = useCallback((e: PointerEvent) => {
        lastPointerRef.current = { x: e.clientX, y: e.clientY };
        setManualTrashHover(isPointerInTrash());
    }, [isPointerInTrash]);

    const attachPointerTracking = useCallback(() => {
        window.addEventListener('pointermove', onPointerMove, { passive: true });
    }, [onPointerMove]);

    const detachPointerTracking = useCallback(() => {
        window.removeEventListener('pointermove', onPointerMove);
        setManualTrashHover(false);
        lastPointerRef.current = null;
    }, [onPointerMove]);

    const handleDragStart = useCallback((event: DragStartEvent) => {
        setActiveKey(String(event.active.id));
        attachPointerTracking();
    }, [attachPointerTracking]);

    const handleDragCancel = useCallback((_event: DragCancelEvent) => {
        setActiveKey(null);
        detachPointerTracking();
    }, [detachPointerTracking]);

    const handleDragEnd = useCallback(
        (event: DragEndEvent) => {
            const { active, over } = event;
            setActiveKey(null);
            const activeId = String(active.id);
            const overId = over ? String(over.id) : '';

            const hitTrash =
                overId === TRASH_DROP_ID ||
                (Array.isArray((event as any).collisions) && (event as any).collisions.some((c: any) => String(c?.id) === TRASH_DROP_ID));

            const manualHit = isPointerInTrash();
            detachPointerTracking();

            if (hitTrash || manualHit) {
                removeSectionKey(activeId);
                return;
            }

            if (!over) return;
            if (activeId === overId) return;

            const oldIndex = orderedKeys.indexOf(activeId);
            const newIndex = orderedKeys.indexOf(overId);
            if (oldIndex < 0 || newIndex < 0) return;

            onSectionOrderChange(arrayMove(orderedKeys, oldIndex, newIndex));
        },
        [detachPointerTracking, isPointerInTrash, onSectionOrderChange, orderedKeys, removeSectionKey]
    );

    const handleUndo = useCallback(() => {
        if (!undoState) return;
        onSectionOrderChange(undoState.prevOrder);
        setHiddenKeys(undoState.prevHidden);
        setUndoState(null);
        if (undoTimerRef.current) {
            window.clearTimeout(undoTimerRef.current);
            undoTimerRef.current = null;
        }
    }, [onSectionOrderChange, setHiddenKeys, undoState]);

    const { isOver, setNodeRef } = useDroppable({ id: TRASH_DROP_ID });
    const setTrashNodeRef = useCallback(
        (node: HTMLDivElement | null) => {
            trashElRef.current = node;
            setNodeRef(node);
        },
        [setNodeRef]
    );

    const collisionDetectionStrategy = useCallback(
        (args: any) => {
            // If the pointer is within the trash zone, prefer it over sortable items.
            const trashContainers = args.droppableContainers?.filter((c: any) => String(c?.id) === TRASH_DROP_ID) || [];
            if (trashContainers.length > 0) {
                const trashHits = pointerWithin({ ...args, droppableContainers: trashContainers });
                if (trashHits && trashHits.length > 0) return trashHits;

                // Fallback: consider it a hit if the dragged item's rect overlaps the trash zone.
                const trashIntersect = rectIntersection({ ...args, droppableContainers: trashContainers });
                if (trashIntersect && trashIntersect.length > 0) return trashIntersect;
            }
            return closestCenter(args);
        },
        []
    );

    return (
        <DndContext
            sensors={sensors}
            collisionDetection={collisionDetectionStrategy}
            measuring={{
                droppable: {
                    strategy: MeasuringStrategy.Always,
                },
            }}
            onDragStart={handleDragStart}
            onDragCancel={handleDragCancel}
            onDragEnd={handleDragEnd}
        >
            <SortableContext items={orderedKeys} strategy={verticalListSortingStrategy}>
                <div className="space-y-4">
                    {orderedRows.map((row) => (
                        <EditableSection
                            key={row.key}
                            id={row.key}
                            editMode={editMode}
                            sectionTitle={row.title}
                        >
                            {row.content}
                        </EditableSection>
                    ))}
                </div>
            </SortableContext>

            {/* Trash drop-zone rail (portal to body; only interactive while dragging) */}
            {canUseDom ? createPortal(
                <div
                    ref={setTrashNodeRef}
                    style={{
                        opacity: activeKey ? 1 : 0,
                        pointerEvents: activeKey ? 'auto' : 'none',
                    }}
                    className={
                        'fixed right-0 top-0 bottom-0 z-[9998] w-[80px] md:w-[160px] rounded-l-2xl border-2 border-dashed px-2 py-4 flex items-stretch justify-center transition-opacity border-red-400 bg-red-50 text-red-700 ' +
                        ((isOver || manualTrashHover)
                            ? 'border-red-600 bg-red-100 text-red-800'
                            : '')
                    }
                    aria-label="Drop here to remove section"
                >
                    <div className="w-full h-full flex flex-col items-center justify-between">
                        <RailLabel text="Drop to delete" />
                        <RailLabel text="Drop to delete" />
                    </div>
                </div>,
                document.body
            ) : null}

            {undoState ? (
                <div className="fixed bottom-4 left-4 z-[9999] rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 flex items-center gap-3">
                    <div className="text-sm text-gray-800">Section removed.</div>
                    <button
                        type="button"
                        onClick={handleUndo}
                        className="text-sm font-semibold text-indigo-700 hover:text-indigo-800"
                    >
                        Undo
                    </button>
                </div>
            ) : null}
        </DndContext>
    );
}

function RailLabel({ text }: { text: string }) {
    return (
        <div
            className="font-black uppercase tracking-[0.45em] text-sm leading-none select-none opacity-95"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
        >
            {text}
        </div>
    );
}
