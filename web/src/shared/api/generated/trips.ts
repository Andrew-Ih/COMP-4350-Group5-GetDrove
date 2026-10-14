// Generated from contracts/openapi/trips.json by `npm run api:generate`. Do not edit.

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
        get?: never;
        put?: never;
        /**
         * Post a trip
         * @description A driver posts a one-off trip to or from campus. The driving route is computed when the trip is posted; if it can't be, nothing is saved.
         */
        post: operations["post_trip__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/mine": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My upcoming trips
         * @description The logged-in user's upcoming trips, soonest first. `role=driver` lists trips they've posted. `role=rider` (trips they've requested) arrives in Sprint 2.
         */
        get: operations["my_trips_mine_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Find trips that pass near the rider
         * @description Scheduled trips with free seats whose driving route passes within walking distance of the rider, excluding the rider's own trips, soonest first. For `to_campus`, `time` is when the rider wants to arrive (trips arriving in the hour before it); for `from_campus`, when they want to leave (trips leaving in the hour after it). An empty list is a normal result. The rider's location is used for matching only and is never stored or shown to drivers.
         */
        get: operations["search_trips_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/{trip_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Trip detail
         * @description One trip. The driver's own end of the trip is returned only to its driver. The pickup point and cost for a specific rider are added in Sprint 2.
         */
        get: operations["get_trip__trip_id__get"];
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
        /** Cost */
        Cost: {
            /**
             * Amountcents
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
             * @description One line explaining the amount.
             * @example 9.3 km at $0.45/km
             */
            explanation: string;
        };
        /**
         * Direction
         * @description Every trip goes to the Fort Garry campus or leaves from it.
         * @enum {string}
         */
        Direction: "to_campus" | "from_campus";
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
             * @example seatsTotal
             */
            field: string;
            /**
             * Message
             * @example Input should be less than or equal to 6
             */
            message: string;
        };
        /**
         * Pickup
         * @description Where the rider would be picked up, on the driver's route.
         */
        Pickup: {
            /**
             * Label
             * @example Osborne St & River Ave
             */
            label: string;
            /** Lat */
            lat: number;
            /** Lng */
            lng: number;
            /**
             * Walkseconds
             * @description Walking time from the rider to this point.
             */
            walkSeconds: number;
        };
        /**
         * Place
         * @description A named point. Labels come from the frontend's address search.
         */
        Place: {
            /**
             * Label
             * @example Wolseley Ave & Arlington St
             */
            label: string;
            /**
             * Lat
             * @example 49.8794
             */
            lat: number;
            /**
             * Lng
             * @example -97.1663
             */
            lng: number;
        };
        /**
         * PostTripRequest
         * @example {
         *       "departureAt": "2026-10-20T13:10:00Z",
         *       "direction": "to_campus",
         *       "place": {
         *         "label": "Wolseley Ave & Arlington St",
         *         "lat": 49.8794,
         *         "lng": -97.1663
         *       },
         *       "seatsTotal": 3
         *     }
         */
        PostTripRequest: {
            /** @description to_campus: the driver starts at `place` and ends at campus. from_campus: the driver starts at campus and ends at `place`. */
            direction: components["schemas"]["Direction"];
            /** @description The driver's end of the trip (usually near home). Never shown to riders. */
            place: components["schemas"]["Place"];
            /**
             * Departureat
             * Format: date-time
             * @description When the driver leaves. Must be in the future.
             * @example 2026-10-20T13:10:00Z
             */
            departureAt: string;
            /**
             * Seatstotal
             * @description Seats offered to riders.
             * @example 3
             */
            seatsTotal: number;
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
            /**
             * Title
             * @example Not found
             */
            title: string;
            /**
             * Status
             * @example 404
             */
            status: number;
            /**
             * Detail
             * @example Trip not found
             */
            detail: string;
            /**
             * Instance
             * @example /api/trips/5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11
             */
            instance: string;
            /**
             * Code
             * @description Stable error name for the frontend to check.
             * @example trip_not_found
             */
            code: string;
            /**
             * Requestid
             * @example b1e2c3d4e5f6
             */
            requestId?: string | null;
            /**
             * Errors
             * @description Only on 422: the fields that were invalid.
             */
            errors?: components["schemas"]["InvalidFieldOut"][] | null;
        };
        /** SearchResult */
        SearchResult: {
            /** @description The driver's end of the trip is null (private). */
            trip: components["schemas"]["Trip"];
            pickup: components["schemas"]["Pickup"];
            /** @description The rider's estimated share. Null if the price can't be computed right now; the trip is still shown. */
            cost: components["schemas"]["Cost"] | null;
        };
        /**
         * Trip
         * @example {
         *       "departureAt": "2026-10-20T13:10:00Z",
         *       "destination": {
         *         "label": "University of Manitoba, Fort Garry campus",
         *         "lat": 49.8075,
         *         "lng": -97.1366
         *       },
         *       "direction": "to_campus",
         *       "distanceMeters": 9800,
         *       "driverId": "0c8d6a1e-7b44-4f0e-8f61-6a2a9d3c5e77",
         *       "durationSeconds": 1320,
         *       "estimatedArrivalAt": "2026-10-20T13:32:00Z",
         *       "id": "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11",
         *       "origin": {
         *         "label": "Wolseley Ave & Arlington St",
         *         "lat": 49.8794,
         *         "lng": -97.1663
         *       },
         *       "seatsAvailable": 3,
         *       "seatsTotal": 3,
         *       "status": "scheduled"
         *     }
         */
        Trip: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Driverid
             * Format: uuid
             */
            driverId: string;
            direction: components["schemas"]["Direction"];
            /** @description Where the trip starts. The driver's own end (their `place`) is only returned to the trip's driver; for everyone else it's null. */
            origin: components["schemas"]["Place"] | null;
            /** @description Where the trip ends. Same privacy rule as `origin`. */
            destination: components["schemas"]["Place"] | null;
            /**
             * Departureat
             * Format: date-time
             */
            departureAt: string;
            /**
             * Estimatedarrivalat
             * Format: date-time
             */
            estimatedArrivalAt: string;
            /**
             * Durationseconds
             * @description Driving time from the computed route.
             */
            durationSeconds: number;
            /**
             * Distancemeters
             * @description Driving distance from the computed route.
             */
            distanceMeters: number;
            /** Seatstotal */
            seatsTotal: number;
            /** Seatsavailable */
            seatsAvailable: number;
            status: components["schemas"]["TripStatus"];
        };
        /**
         * TripStatus
         * @enum {string}
         */
        TripStatus: "scheduled" | "in_progress" | "completed" | "cancelled";
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
    post_trip__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PostTripRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Trip"];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, including seats outside 1-6 or a departure in the past (code `invalid_input / departure_in_past`) */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The route couldn't be computed right now (code `routing_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    my_trips_mine_get: {
        parameters: {
            query?: {
                role?: "driver" | "rider";
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
                    "application/json": components["schemas"]["Trip"][];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
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
    search_trips_search_get: {
        parameters: {
            query: {
                /** @description Rider's latitude. */
                lat: number;
                /** @description Rider's longitude. */
                lng: number;
                direction: components["schemas"]["Direction"];
                /** @description Arrive by (to_campus) or leave after (from_campus). */
                time: string;
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
                    "application/json": components["schemas"]["SearchResult"][];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
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
            /** @description Matching is unavailable right now (code `routing_unavailable`) */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_trip__trip_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trip_id: string;
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
                    "application/json": components["schemas"]["Trip"];
                };
            };
            /** @description Missing or invalid access token (code `unauthorized`) */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No trip with this ID (code `trip_not_found`) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
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
