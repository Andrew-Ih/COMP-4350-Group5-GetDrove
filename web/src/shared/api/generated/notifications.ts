// Generated from contracts/openapi/notifications.json by `npm run api:generate`. Do not edit.

export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My notifications
         * @description The logged-in user's latest notifications, newest first, and how many are unread.
         */
        get: operations["list_notifications__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/read-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark all as read */
        post: operations["mark_all_read_read_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/{notification_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark one as read */
        post: operations["mark_read__notification_id__read_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** HealthOut */
        HealthOut: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Service */
            service: string;
        };
        /** InvalidFieldOut */
        InvalidFieldOut: {
            /**
             * Field
             * @example limit
             */
            field: string;
            /**
             * Message
             * @example Input should be less than or equal to 100
             */
            message: string;
        };
        /** Notification */
        Notification: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            type: components["schemas"]["NotificationType"];
            /**
             * Title
             * @example Request accepted
             */
            title: string;
            /**
             * Body
             * @example Maya accepted your request for Monday at 7:45 AM.
             */
            body: string;
            /**
             * Tripid
             * @description The trip it's about, to link to it.
             */
            tripId: string | null;
            /**
             * Requestid
             * @description The seat request it's about, if any.
             */
            requestId: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Readat */
            readAt: string | null;
        };
        /** NotificationList */
        NotificationList: {
            /**
             * Items
             * @description Newest first.
             */
            items: components["schemas"]["Notification"][];
            /**
             * Unreadcount
             * @description All unread notifications, not just these.
             */
            unreadCount: number;
        };
        /**
         * NotificationType
         * @enum {string}
         */
        NotificationType: "seat_requested" | "request_accepted" | "request_declined" | "request_cancelled" | "trip_cancelled" | "driver_approved" | "driver_rejected" | "payment_failed" | "trip_reminder";
        /**
         * Problem
         * @description Every error response (RFC 9457 Problem Details, `application/problem+json`).
         */
        Problem: {
            /**
             * Type
             * @default about:blank
             */
            type: string;
            /** Title */
            title: string;
            /** Status */
            status: number;
            /** Detail */
            detail: string;
            /** Instance */
            instance: string;
            /**
             * Code
             * @description Stable error name for the frontend to check.
             */
            code: string;
            /** Requestid */
            requestId?: string | null;
            /**
             * Errors
             * @description Only on 422: the fields that were invalid.
             */
            errors?: components["schemas"]["InvalidFieldOut"][] | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
    list_notifications__get: {
        parameters: {
            query?: {
                /** @description How many to return. */
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationList"];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "limit",
                     *           "message": "Input should be less than or equal to 100"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    mark_all_read_read_all_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/read-all",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    mark_read__notification_id__read_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/{notification_id}/read",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No notification with this ID for you (code `notification_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Not Found",
                     *       "status": 404,
                     *       "detail": "No notification with this ID for you",
                     *       "instance": "/{notification_id}/read",
                     *       "code": "notification_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input; `errors` lists the fields (code `invalid_input`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unprocessable Content",
                     *       "status": 422,
                     *       "detail": "Invalid input",
                     *       "instance": "/{notification_id}/read",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "limit",
                     *           "message": "Input should be less than or equal to 100"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
