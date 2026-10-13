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
            /** Field */
            field: string;
            /** Message */
            message: string;
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
             * @example invalid_input
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
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
