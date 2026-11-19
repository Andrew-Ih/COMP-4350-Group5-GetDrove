// Generated from contracts/openapi/payments.json by `npm run api:generate`. Do not edit.

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
    "/internal/quotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Price a rider's share
         * @description The rider's estimated cost for travelling `distanceMeters` in the car: $0.45 per km, rounded to the nearest 5 cents, with a $2.00 minimum, plus a one-line explanation. The quote shown when requesting is the amount charged unless the trip changes.
         */
        post: operations["quote_internal_quotes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/customers/{user_id}/card": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Does this rider have a card?
         * @description For Trips: a rider needs a saved card before requesting a seat.
         */
        get: operations["card_status_internal_customers__user_id__card_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/setup-intent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start adding a card
         * @description Creates a Stripe SetupIntent for the logged-in rider (and their Stripe customer, the first time). The frontend passes `clientSecret` to Stripe Elements.
         */
        post: operations["create_setup_intent_setup_intent_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/methods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My saved cards
         * @description Brand, last 4 digits and expiry only. An empty list means no card yet. Read from Stripe, not a copy in our database, so a card is listed as soon as `stripe.confirmCardSetup` succeeds: the frontend refetches this right after it and shows a saving state until it returns.
         */
        get: operations["payment_methods_methods_get"];
        put?: never;
        post?: never;
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
        /** CardStatus */
        CardStatus: {
            /**
             * Userid
             * Format: uuid
             */
            userId: string;
            /** Hascard */
            hasCard: boolean;
        };
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
            /** Field */
            field: string;
            /** Message */
            message: string;
        };
        /**
         * PaymentMethod
         * @description A saved card. Only what's needed to recognise it.
         */
        PaymentMethod: {
            /**
             * Id
             * @description Stripe's payment method ID.
             * @example pm_1Nx…
             */
            id: string;
            /**
             * Brand
             * @example visa
             */
            brand: string;
            /**
             * Last4
             * @example 4242
             */
            last4: string;
            /**
             * Expmonth
             * @example 12
             */
            expMonth: number;
            /**
             * Expyear
             * @example 2030
             */
            expYear: number;
            /**
             * Isdefault
             * @description The card holds are placed on: the most recently added one. Removing cards and choosing the default aren't part of Sprint 2.
             */
            isDefault: boolean;
        };
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
             * @description Stable error name.
             */
            code: string;
            /** Requestid */
            requestId?: string | null;
            /** Errors */
            errors?: components["schemas"]["InvalidFieldOut"][] | null;
        };
        /** Quote */
        Quote: {
            /**
             * Amountcents
             * @description $0.45 per km, rounded to the nearest 5 cents, at least $2.00.
             * @example 420
             */
            amountCents: number;
            /**
             * Currency
             * @default CAD
             * @constant
             */
            currency: "CAD";
            /**
             * Explanation
             * @description One line for the rider.
             * @example 9.3 km at $0.45/km
             */
            explanation: string;
        };
        /** QuoteRequest */
        QuoteRequest: {
            /**
             * Distancemeters
             * @description How far the rider travels in the car.
             * @example 9300
             */
            distanceMeters: number;
        };
        /** SetupIntent */
        SetupIntent: {
            /**
             * Clientsecret
             * @description Pass to Stripe Elements (`stripe.confirmCardSetup`). Card details go straight to Stripe and never reach our servers.
             * @example seti_1Nx…_secret_…
             */
            clientSecret: string;
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
    quote_internal_quotes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuoteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Quote"];
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
                     *       "instance": "/internal/quotes",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "fieldName",
                     *           "message": "Field required"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    card_status_internal_customers__user_id__card_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
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
                    "application/json": components["schemas"]["CardStatus"];
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
                     *       "instance": "/internal/customers/{user_id}/card",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "fieldName",
                     *           "message": "Field required"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    create_setup_intent_setup_intent_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SetupIntent"];
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
                     *       "instance": "/setup-intent",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Stripe can't be reached right now (code `payments_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Service Unavailable",
                     *       "status": 503,
                     *       "detail": "Stripe can't be reached right now",
                     *       "instance": "/setup-intent",
                     *       "code": "payments_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    payment_methods_methods_get: {
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
                    "application/json": components["schemas"]["PaymentMethod"][];
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
                     *       "instance": "/methods",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Stripe can't be reached right now (code `payments_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Service Unavailable",
                     *       "status": 503,
                     *       "detail": "Stripe can't be reached right now",
                     *       "instance": "/methods",
                     *       "code": "payments_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
