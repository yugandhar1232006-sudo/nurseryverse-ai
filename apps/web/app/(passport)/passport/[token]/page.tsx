"use client";

import { useParams } from "next/navigation";

import { PublicPassportView } from "@/components/passport/public-passport-view";

/**
 * `/passport/[token]` -- the public, unauthenticated Plant Passport
 * certificate. This is the URL `QRService.qr_payload_url()` encodes for
 * every physical QR tag (see apps/api/app/services/passport_service.py),
 * so this exact route, with no `(app)`-style auth gate anywhere above it
 * in the tree, is what a customer's phone actually opens after scanning a
 * plant tag.
 */
export default function PublicPassportPage() {
  const params = useParams<{ token: string }>();
  return <PublicPassportView token={params.token} />;
}
