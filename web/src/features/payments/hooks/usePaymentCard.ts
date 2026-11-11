"use client";

import { useQuery } from "@tanstack/react-query";

import type { ApiError } from "@/shared/api";

import { getPaymentMethods } from "../api/paymentsApi";
import type { PaymentMethod } from "../model/card";

/** The student's saved cards. */
export function usePaymentMethods() {
  return useQuery<PaymentMethod[], ApiError>({ queryKey: ["payments", "methods"], queryFn: getPaymentMethods });
}
