"use client";

import { createContext, type ReactNode } from "react";

/**
 * What the header shows for notifications on wide screens. The app fills it with the
 * notification bell (features/notifications), since shared/ can't import features; when
 * it's empty (e.g. in tests), the header shows a plain link to /notifications.
 */
export const HeaderBellContext = createContext<ReactNode>(null);
