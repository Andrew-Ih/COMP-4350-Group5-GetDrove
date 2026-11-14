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
    "/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Post a recurring weekday trip
         * @description Creates one trip per matching weekday from the first departure up to `endDate`, all at the same Winnipeg time. Each is its own trip that riders request separately. Days that clash with the driver's other trips are skipped and listed in `skippedDates`.
         */
        post: operations["post_trip_series_series_post"];
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
         * My trips as a driver
         * @description Trips the logged-in user has posted, including cancelled ones. A rider's trips are at `GET /requests/mine`.
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
    "/requests/mine": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My trips as a rider
         * @description Trips the logged-in user has requested a seat on, each with their request and its status (pending, accepted, declined, cancelled, expired, payment failed). Cancelled trips are included, not removed.
         */
        get: operations["my_requests_requests_mine_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auto-accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My auto-accept rules
         * @description The driver's rules. If they've never set any: off, 5 minutes, no minimum rating.
         */
        get: operations["get_auto_accept_auto_accept_get"];
        /**
         * Set my auto-accept rules
         * @description A request is accepted automatically when auto-accept is on, its pickup adds at most `maxDetourMinutes` (`detourSeconds <= maxDetourMinutes * 60`), the rider is rated at least `minRating` (riders with no ratings yet pass), and a seat is free. Otherwise it waits for the driver. Changes apply to new requests only.
         */
        put: operations["put_auto_accept_auto_accept_put"];
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
    "/requests/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One seat request
         * @description For the rider who made it or the trip's driver, e.g. to see whether a pending request was accepted.
         */
        get: operations["get_request_requests__request_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/requests/{request_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept a request
         * @description The trip's driver gives the rider a seat. Taking the seat is atomic: when two requests race for the last seat, exactly one wins and the other gets `seat_taken`.
         */
        post: operations["accept_request_requests__request_id__accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/requests/{request_id}/decline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Decline a request
         * @description The trip's driver turns down a pending request, or removes an accepted rider before the trip starts. An accepted rider's seat is freed straight away.
         */
        post: operations["decline_request_requests__request_id__decline_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/requests/{request_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel my request
         * @description The rider withdraws a pending or accepted request before the trip starts. An accepted seat is freed straight away and any hold on their card is released.
         */
        post: operations["cancel_request_requests__request_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/series/{series_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel a recurring series
         * @description Cancels every trip in the series that hasn't started. Riders are notified and holds released, as for a single cancellation. Returns the trips cancelled.
         */
        post: operations["cancel_series_series__series_id__cancel_post"];
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
         * @description One trip, with up to 3 pickup points for the rider at `lat`/`lng` (each with its walking time and price) and the caller's own request on it, if any. The driver's own end of the trip is returned only to its driver. Send `lat` and `lng` together or not at all; they're used to find pickup points and never stored. `exclude` leaves out pickup points the rider rejected (#136), so the next best come back instead; it's ignored without `lat` and `lng`.
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
    "/{trip_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel a trip
         * @description The driver cancels a trip that hasn't started. It disappears from search but stays in My trips as cancelled; riders are notified and holds released. Cancelling less than an hour before departure is recorded as a late cancellation.
         */
        post: operations["cancel_trip__trip_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/{trip_id}/requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Requests on my trip
         * @description For the trip's driver: pending requests first, then accepted ones, each with the rider's rating and no-shows, their pickup point and the detour it adds.
         */
        get: operations["trip_requests__trip_id__requests_get"];
        put?: never;
        /**
         * Request a seat
         * @description The rider asks for a seat, picked up at one of the trip detail's pickup points. The price is saved with the request and is what gets charged. The request is `pending` until the driver decides, or `accepted` straight away if it meets the driver's auto-accept rules. The rider needs a saved card first. Send the same `exclude` the trip detail was loaded with, so a point offered after the rider rejected others is still accepted.
         */
        post: operations["request_seat__trip_id__requests_post"];
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
        /** AutoAcceptRules */
        AutoAcceptRules: {
            /**
             * Enabled
             * @description Applies to new requests only.
             */
            enabled: boolean;
            /**
             * Maxdetourminutes
             * @description Accept only if the pickup adds at most this much: a request's `detourSeconds` must be at most `maxDetourMinutes * 60`.
             * @example 5
             */
            maxDetourMinutes: number;
            /**
             * Minrating
             * @description Accept only riders rated at least this. Null: any rating. Riders with no ratings yet always pass.
             * @example 4
             */
            minRating: number | null;
        };
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
        /** DriverPickup */
        DriverPickup: {
            /**
             * Label
             * @example Osborne St & River Ave
             */
            label: string;
            /** Lat */
            lat: number;
            /** Lng */
            lng: number;
        };
        /**
         * DriverRequestView
         * @description A request on one of the driver's trips, with what they need to decide.
         */
        DriverRequestView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["RequestStatus"];
            rider: components["schemas"]["RiderSummary"];
            /** @description Only the pickup point, never where the rider is. */
            pickup: components["schemas"]["DriverPickup"];
            /**
             * Pickuporder
             * @description Place in the pickup order (1 = first). Accepted requests only.
             */
            pickupOrder: number | null;
            /**
             * Detourseconds
             * @description Extra driving time this pickup adds. Null if it couldn't be worked out: show an error state, not a number.
             */
            detourSeconds: number | null;
            cost: components["schemas"]["Cost"];
            /** Autoaccepted */
            autoAccepted: boolean;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Decidedat */
            decidedAt: string | null;
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
         * PickupOption
         * @description A point on the driver's route where this rider could be picked up.
         */
        PickupOption: {
            /**
             * Id
             * @description Opaque ID from Routing. Send it back when requesting a seat.
             * @example s42
             */
            id: string;
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
            /** @description This rider's share if picked up here. Null if it can't be priced right now. */
            cost: components["schemas"]["Cost"] | null;
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
         * PostTripSeriesRequest
         * @example {
         *       "departureAt": "2026-11-16T13:10:00Z",
         *       "direction": "to_campus",
         *       "endDate": "2026-12-11",
         *       "place": {
         *         "label": "Wolseley Ave & Arlington St",
         *         "lat": 49.8794,
         *         "lng": -97.1663
         *       },
         *       "seatsTotal": 3,
         *       "weekdays": [
         *         "mon",
         *         "wed",
         *         "fri"
         *       ]
         *     }
         */
        PostTripSeriesRequest: {
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
            /**
             * Weekdays
             * @description The weekdays it repeats on. Each one at most once.
             * @example [
             *       "mon",
             *       "wed",
             *       "fri"
             *     ]
             */
            weekdays: ("mon" | "tue" | "wed" | "thu" | "fri")[];
            /**
             * Enddate
             * Format: date
             * @description The last day a trip can be on (Winnipeg date). After the first departure and at most 16 weeks after it.
             * @example 2026-12-11
             */
            endDate: string;
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
        /** RequestPickup */
        RequestPickup: {
            /**
             * Label
             * @example Osborne St & River Ave
             */
            label: string;
            /** Lat */
            lat: number;
            /** Lng */
            lng: number;
            /** Walkseconds */
            walkSeconds: number;
        };
        /**
         * RequestStatus
         * @enum {string}
         */
        RequestStatus: "pending" | "accepted" | "declined" | "cancelled" | "expired" | "payment_failed";
        /** RiderSummary */
        RiderSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Firstname
             * @example Priya
             */
            firstName: string;
            /**
             * Rating
             * @description Average rating; null if they have no ratings yet.
             */
            rating: number | null;
            /** Ratingcount */
            ratingCount: number;
            /** Noshowcount */
            noShowCount: number;
        };
        /** RiderTrip */
        RiderTrip: {
            /** @description The driver's end is null (private). */
            trip: components["schemas"]["Trip"];
            request: components["schemas"]["SeatRequest"];
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
         * SeatRequest
         * @description A rider's request for a seat, as the rider sees it.
         */
        SeatRequest: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Tripid
             * Format: uuid
             */
            tripId: string;
            /**
             * Riderid
             * Format: uuid
             */
            riderId: string;
            status: components["schemas"]["RequestStatus"];
            pickup: components["schemas"]["RequestPickup"];
            /** @description Saved when the request was made: this is what gets held and charged. */
            cost: components["schemas"]["Cost"];
            /** Autoaccepted */
            autoAccepted: boolean;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Decidedat
             * @description When it was accepted, declined, cancelled or expired.
             */
            decidedAt: string | null;
        };
        /**
         * SeatRequestBody
         * @example {
         *       "lat": 49.8722,
         *       "lng": -97.1561,
         *       "pickupId": "s42"
         *     }
         * @example {
         *       "exclude": [
         *         "s42",
         *         "s45"
         *       ],
         *       "lat": 49.8722,
         *       "lng": -97.1561,
         *       "pickupId": "s50"
         *     }
         */
        SeatRequestBody: {
            /**
             * Lat
             * @description The rider's location. Used to check the pickup, never stored.
             */
            lat: number;
            /** Lng */
            lng: number;
            /**
             * Pickupid
             * @description One of the trip detail's `pickups`.
             */
            pickupId: string;
            /**
             * Exclude
             * @description The same `exclude` the trip detail was loaded with (#136), so a pickup point that was only offered because the rider rejected others is still accepted (#299). Passed on to Routing, never stored.
             */
            exclude?: string[];
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
            /**
             * Seriesid
             * @description The recurring series this trip belongs to, if any.
             */
            seriesId?: string | null;
        };
        /** TripDetail */
        TripDetail: {
            /** @description The driver's own end is null unless you're the driver. */
            trip: components["schemas"]["Trip"];
            /** @description The driver's vehicle, with its plate, so an accepted rider can find their car. Only for the trip's driver and riders with an accepted request on it; null for everyone else (make, model and colour are on the driver's public profile). */
            vehicle: components["schemas"]["TripVehicle"] | null;
            /**
             * Pickups
             * @description Up to 3 pickup points, best first. Empty if `lat`/`lng` weren't sent or the trip doesn't pass within walking distance of them.
             */
            pickups: components["schemas"]["PickupOption"][];
            /** @description Your pending or accepted request on this trip, if you have one. */
            myRequest: components["schemas"]["SeatRequest"] | null;
        };
        /** TripSeriesResult */
        TripSeriesResult: {
            /**
             * Seriesid
             * Format: uuid
             */
            seriesId: string;
            /**
             * Trips
             * @description The trips created, one per matching day.
             */
            trips: components["schemas"]["Trip"][];
            /**
             * Skippeddates
             * @description Days left out because they clash with the driver's other trips.
             */
            skippedDates: string[];
        };
        /**
         * TripStatus
         * @enum {string}
         */
        TripStatus: "scheduled" | "in_progress" | "completed" | "cancelled";
        /** TripVehicle */
        TripVehicle: {
            /**
             * Make
             * @example Honda
             */
            make: string;
            /**
             * Model
             * @example Civic
             */
            model: string;
            /**
             * Colour
             * @example Blue
             */
            colour: string;
            /**
             * Plate
             * @example ABC123
             */
            plate: string;
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
            /** @description Only approved drivers can post trips (code `driver_not_approved`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only approved drivers can post trips",
                     *       "instance": "/",
                     *       "code": "driver_not_approved",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, including seats outside 1-6, an unroutable place, or a departure in the past (code `invalid_input / departure_in_past`) */
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
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The route couldn't be computed right now (code `routing_unavailable`) */
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
                     *       "detail": "The route couldn't be computed right now",
                     *       "instance": "/",
                     *       "code": "routing_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    post_trip_series_series_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PostTripSeriesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TripSeriesResult"];
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
                     *       "instance": "/series",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only approved drivers can post trips (code `driver_not_approved`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only approved drivers can post trips",
                     *       "instance": "/series",
                     *       "code": "driver_not_approved",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, including a weekday listed twice, an end date before the first departure or more than 16 weeks after it, or a departure in the past (code `invalid_input / departure_in_past`) */
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
                     *       "instance": "/series",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The route couldn't be computed right now (code `routing_unavailable`) */
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
                     *       "detail": "The route couldn't be computed right now",
                     *       "instance": "/series",
                     *       "code": "routing_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    my_trips_mine_get: {
        parameters: {
            query?: {
                /** @description Kept for older clients; always `driver`. */
                role?: "driver";
                /** @description Upcoming (soonest first) or past (most recent first). */
                when?: "upcoming" | "past";
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
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/mine",
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
                     *       "instance": "/mine",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    my_requests_requests_mine_get: {
        parameters: {
            query?: {
                /** @description Upcoming (soonest first) or past (most recent first). */
                when?: "upcoming" | "past";
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
                    "application/json": components["schemas"]["RiderTrip"][];
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
                     *       "instance": "/requests/mine",
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
                     *       "instance": "/requests/mine",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_auto_accept_auto_accept_get: {
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
                    "application/json": components["schemas"]["AutoAcceptRules"];
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
                     *       "instance": "/auto-accept",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    put_auto_accept_auto_accept_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutoAcceptRules"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutoAcceptRules"];
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
                     *       "instance": "/auto-accept",
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
                     *       "instance": "/auto-accept",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
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
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/search",
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
                     *       "instance": "/search",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Matching is unavailable right now (code `routing_unavailable`) */
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
                     *       "detail": "Matching is unavailable right now",
                     *       "instance": "/search",
                     *       "code": "routing_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_request_requests__request_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
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
                    "application/json": components["schemas"]["SeatRequest"];
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
                     *       "instance": "/requests/{request_id}",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Not your request or your trip (code `forbidden`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Not your request or your trip",
                     *       "instance": "/requests/{request_id}",
                     *       "code": "forbidden",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No request with this ID (code `request_not_found`) */
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
                     *       "detail": "No request with this ID",
                     *       "instance": "/requests/{request_id}",
                     *       "code": "request_not_found",
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
                     *       "instance": "/requests/{request_id}",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    accept_request_requests__request_id__accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
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
                    "application/json": components["schemas"]["SeatRequest"];
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
                     *       "instance": "/requests/{request_id}/accept",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the trip's driver can accept (code `not_trip_driver`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the trip's driver can accept",
                     *       "instance": "/requests/{request_id}/accept",
                     *       "code": "not_trip_driver",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No request with this ID (code `request_not_found`) */
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
                     *       "detail": "No request with this ID",
                     *       "instance": "/requests/{request_id}/accept",
                     *       "code": "request_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No seat left, or the request isn't pending (code `seat_taken / request_not_pending`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "No seat left, or the request isn't pending",
                     *       "instance": "/requests/{request_id}/accept",
                     *       "code": "seat_taken",
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
                     *       "instance": "/requests/{request_id}/accept",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    decline_request_requests__request_id__decline_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
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
                    "application/json": components["schemas"]["SeatRequest"];
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
                     *       "instance": "/requests/{request_id}/decline",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the trip's driver can decline (code `not_trip_driver`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the trip's driver can decline",
                     *       "instance": "/requests/{request_id}/decline",
                     *       "code": "not_trip_driver",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No request with this ID (code `request_not_found`) */
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
                     *       "detail": "No request with this ID",
                     *       "instance": "/requests/{request_id}/decline",
                     *       "code": "request_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only pending or accepted requests on a trip that hasn't started can be declined (code `request_not_decidable`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "Only pending or accepted requests on a trip that hasn't started can be declined",
                     *       "instance": "/requests/{request_id}/decline",
                     *       "code": "request_not_decidable",
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
                     *       "instance": "/requests/{request_id}/decline",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    cancel_request_requests__request_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
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
                    "application/json": components["schemas"]["SeatRequest"];
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
                     *       "instance": "/requests/{request_id}/cancel",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the rider who made it can cancel it (code `not_your_request`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the rider who made it can cancel it",
                     *       "instance": "/requests/{request_id}/cancel",
                     *       "code": "not_your_request",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No request with this ID (code `request_not_found`) */
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
                     *       "detail": "No request with this ID",
                     *       "instance": "/requests/{request_id}/cancel",
                     *       "code": "request_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only pending or accepted requests on a trip that hasn't started can be cancelled (code `request_not_cancellable`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "Only pending or accepted requests on a trip that hasn't started can be cancelled",
                     *       "instance": "/requests/{request_id}/cancel",
                     *       "code": "request_not_cancellable",
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
                     *       "instance": "/requests/{request_id}/cancel",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    cancel_series_series__series_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                series_id: string;
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
                    "application/json": components["schemas"]["Trip"][];
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
                     *       "instance": "/series/{series_id}/cancel",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the series' driver can cancel it (code `not_trip_driver`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the series' driver can cancel it",
                     *       "instance": "/series/{series_id}/cancel",
                     *       "code": "not_trip_driver",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No series with this ID (code `series_not_found`) */
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
                     *       "detail": "No series with this ID",
                     *       "instance": "/series/{series_id}/cancel",
                     *       "code": "series_not_found",
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
                     *       "instance": "/series/{series_id}/cancel",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_trip__trip_id__get: {
        parameters: {
            query?: {
                /** @description Rider's latitude. */
                lat?: number | null;
                /** @description Rider's longitude. */
                lng?: number | null;
                /** @description IDs of pickup points the rider rejected, repeated: `?exclude=s42&exclude=s45`. At most 20. */
                exclude?: string[] | null;
            };
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
                    "application/json": components["schemas"]["TripDetail"];
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
                     *       "instance": "/{trip_id}",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No trip with this ID (code `trip_not_found`) */
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
                     *       "detail": "No trip with this ID",
                     *       "instance": "/{trip_id}",
                     *       "code": "trip_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, including only one of `lat` and `lng` (code `invalid_input`) */
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
                     *       "instance": "/{trip_id}",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Pickup points can't be worked out right now (code `routing_unavailable`) */
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
                     *       "detail": "Pickup points can't be worked out right now",
                     *       "instance": "/{trip_id}",
                     *       "code": "routing_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    cancel_trip__trip_id__cancel_post: {
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
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Unauthorized",
                     *       "status": 401,
                     *       "detail": "Missing or invalid access token",
                     *       "instance": "/{trip_id}/cancel",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the trip's driver can cancel it (code `not_trip_driver`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the trip's driver can cancel it",
                     *       "instance": "/{trip_id}/cancel",
                     *       "code": "not_trip_driver",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No trip with this ID (code `trip_not_found`) */
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
                     *       "detail": "No trip with this ID",
                     *       "instance": "/{trip_id}/cancel",
                     *       "code": "trip_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The trip has already started, finished or been cancelled (code `trip_not_cancellable`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "The trip has already started, finished or been cancelled",
                     *       "instance": "/{trip_id}/cancel",
                     *       "code": "trip_not_cancellable",
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
                     *       "instance": "/{trip_id}/cancel",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    trip_requests__trip_id__requests_get: {
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
                    "application/json": components["schemas"]["DriverRequestView"][];
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
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Only the trip's driver can see its requests (code `not_trip_driver`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "Only the trip's driver can see its requests",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "not_trip_driver",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No trip with this ID (code `trip_not_found`) */
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
                     *       "detail": "No trip with this ID",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "trip_not_found",
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
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The riders' details can't be loaded right now (code `accounts_unavailable`) */
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
                     *       "detail": "The riders' details can't be loaded right now",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "accounts_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    request_seat__trip_id__requests_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trip_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SeatRequestBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeatRequest"];
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
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "unauthorized",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description You can't request a seat on your own trip (code `own_trip`) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Forbidden",
                     *       "status": 403,
                     *       "detail": "You can't request a seat on your own trip",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "own_trip",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description No trip with this ID (code `trip_not_found`) */
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
                     *       "detail": "No trip with this ID",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "trip_not_found",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Already on this trip, another request overlaps in time, no seats left, the trip isn't open for requests, or no saved card (code `already_requested / overlapping_request / trip_full / trip_not_open / card_required`) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    /**
                     * @example {
                     *       "type": "about:blank",
                     *       "title": "Conflict",
                     *       "status": 409,
                     *       "detail": "Already on this trip, another request overlaps in time, no seats left, the trip isn't open for requests, or no saved card",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "already_requested",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Invalid input, or the pickup point isn't available from where you are (code `invalid_input / pickup_not_available`) */
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
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "invalid_input",
                     *       "requestId": "b1e2c3d4e5f6",
                     *       "errors": [
                     *         {
                     *           "field": "seatsTotal",
                     *           "message": "Input should be less than or equal to 6"
                     *         }
                     *       ]
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description The pickup or detour can't be worked out right now, or the price or saved card can't be checked (code `routing_unavailable / payments_unavailable`) */
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
                     *       "detail": "The pickup or detour can't be worked out right now, or the price or saved card can't be checked",
                     *       "instance": "/{trip_id}/requests",
                     *       "code": "routing_unavailable",
                     *       "requestId": "b1e2c3d4e5f6"
                     *     }
                     */
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
