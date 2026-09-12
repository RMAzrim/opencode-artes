---
id: form-validation-schema-builder
file_path: skills/form-validation-schema-builder/form-validation-schema-builder.md
name: Form Validation & Schema Builder
category: frontend
tags: [react-hook-form, zod, validation, typescript]
author: opencode-core
version: 1.0.0
description: Builds robust, type-safe interactive web forms featuring complex validation logic, real-time error feedback, and seamless client-server schema synchronization.
---

# Form Validation & Schema Builder

## 1. System Architecture & Prerequisites
- Runtime: Node.js >= 20.11.0, npm >= 10.
- Framework: Next.js 15.1.6 with React 19.
- Dependencies: `react-hook-form@^7.54.2`, `@hookform/resolvers@^3.10.0`, `zod@^3.24.1`, `next@15.1.6`, `react@19.0.0`, `react-dom@19.0.0`.
- Dev dependencies: `typescript@^5.7.3`, `@types/react@^19.0.7`, `@types/react-dom@^19.0.3`, `@types/node@^22.10.7`.
- Architecture rules enforced by this blueprint:
  - One Zod schema is the single source of truth. React Hook Form binds to it via `zodResolver`; TypeScript types are inferred with `z.infer<typeof schema>` so the client, server, and store cannot diverge.
  - Validation is progressive: each step of the registration flow is its own Zod schema; navigation gates on `trigger([...stepFields])` before advancing.
  - A final discriminated-union `safeParse` re-validates the whole bundle on submit, mapping any failure back to its owning step before anything is persisted.
  - Errors are rendered through one typed generic `<Field>` wrapper with `aria-invalid` and `aria-describedby` wiring.

## 2. Input/Output Data Contracts
JSON Schema for the form configuration inputs:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "steps": {
      "type": "array",
      "items": { "enum": ["account", "address", "confirm"] },
      "default": ["account", "address", "confirm"]
    },
    "validationMode": { "enum": ["onBlur", "onTouched", "onChange"], "default": "onTouched" },
    "revalidateFinalPayload": { "type": "boolean", "default": true }
  },
  "required": ["steps"]
}
```

Output artifacts (exact paths):
- `lib/validators.ts` (shared Zod schemas + `z.infer` types + discriminated-union bundle parser)
- `components/Field.tsx` (typed generic field wrapper)
- `components/RegistrationForm.tsx` (progressive 3-step form)
- `app/page.tsx` (App usage example), `app/layout.tsx`, `package.json`

Data contract for the final submission payload:

```ts
type RegistrationFormFields = {
  email: string;
  password: string;
  confirmPassword: string;
  fullName: string;
  addressLine1: string;
  addressLine2?: string;
  city: string;
  zip: string;
  country: string;
  phone: string;
  termsAccepted: boolean;
  marketingOptIn?: boolean;
};
```

## 3. Production Reference Implementation
One complete, self-contained implementation. Every file is final and runnable:

```
# =========================================================
# FILE: package.json
# =========================================================
{
  "name": "form-validation-schema-builder",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.10.0",
    "next": "15.1.6",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "react-hook-form": "^7.54.2",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@types/node": "^22.10.7",
    "@types/react": "^19.0.7",
    "@types/react-dom": "^19.0.3",
    "typescript": "^5.7.3"
  }
}

# =========================================================
# FILE: lib/validators.ts
# =========================================================
import { z } from "zod";

const emailSchema = z
  .string()
  .trim()
  .min(1, "Email is required")
  .max(254, "Email is too long")
  .email("Enter a valid email address");

const phoneSchema = z
  .string()
  .trim()
  .min(1, "Phone is required")
  .max(20, "Phone is too long")
  .regex(/^\+?[0-9\s()-]{7,20}$/, "Enter a valid phone, e.g. +1 555 123 4567");

const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(128, "Password must be at most 128 characters")
  .regex(/[A-Z]/, "Password needs an uppercase letter")
  .regex(/[a-z]/, "Password needs a lowercase letter")
  .regex(/[0-9]/, "Password needs a number");

export const accountStepSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your password")
  })
  .superRefine((values, ctx) => {
    if (values.password !== values.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["confirmPassword"],
        message: "Passwords do not match"
      });
    }
  });

export const addressStepSchema = z.object({
  fullName: z.string().trim().min(2, "Full name is required").max(120, "Full name is too long"),
  addressLine1: z.string().trim().min(3, "Street address is required").max(200, "Street address is too long"),
  addressLine2: z.string().trim().max(200, "Address line too long").optional(),
  city: z.string().trim().min(2, "City is required").max(80, "City is too long"),
  zip: z
    .string()
    .trim()
    .min(1, "Postal code is required")
    .regex(/^[0-9]{4,10}$/, "Postal code must be 4-10 digits"),
  country: z.string().min(2, "Select a country code").max(3, "Use the 2-3 letter ISO code"),
  phone: phoneSchema
});

export const confirmStepSchema = z.object({
  termsAccepted: z.boolean().refine((value) => value === true, "You must accept the terms and conditions"),
  marketingOptIn: z.boolean().optional()
});

export const registrationFormSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your password"),
    fullName: z.string().trim().min(2, "Full name is required").max(120, "Full name is too long"),
    addressLine1: z.string().trim().min(3, "Street address is required").max(200, "Street address is too long"),
    addressLine2: z.string().trim().max(200, "Address line too long").optional(),
    city: z.string().trim().min(2, "City is required").max(80, "City is too long"),
    zip: z
      .string()
      .trim()
      .min(1, "Postal code is required")
      .regex(/^[0-9]{4,10}$/, "Postal code must be 4-10 digits"),
    country: z.string().min(2, "Select a country code").max(3, "Use the 2-3 letter ISO code"),
    phone: phoneSchema,
    termsAccepted: z.boolean().refine((value) => value === true, "You must accept the terms and conditions"),
    marketingOptIn: z.boolean().optional()
  })
  .superRefine((values, ctx) => {
    if (values.password !== values.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["confirmPassword"],
        message: "Passwords do not match"
      });
    }
  });

export const registrationBundleSchema = z.discriminatedUnion("step", [
  z.object({ step: z.literal("account"), data: accountStepSchema }),
  z.object({ step: z.literal("address"), data: addressStepSchema }),
  z.object({ step: z.literal("confirm"), data: confirmStepSchema })
]);

export type RegistrationFormFields = z.infer<typeof registrationFormSchema>;
export type AccountFields = z.infer<typeof accountStepSchema>;
export type AddressFields = z.infer<typeof addressStepSchema>;
export type ConfirmFields = z.infer<typeof confirmStepSchema>;
export type RegistrationBundleInput = z.input<typeof registrationBundleSchema>;
export type RegistrationBundle = z.infer<typeof registrationBundleSchema>;

# =========================================================
# FILE: components/Field.tsx
# =========================================================
"use client";

import type { FieldErrors, FieldValues, Path, UseFormRegister } from "react-hook-form";

type FieldProps<TFormValues extends FieldValues> = {
  name: Path<TFormValues>;
  label: string;
  type?: "text" | "email" | "password" | "tel";
  placeholder?: string;
  autoComplete?: string;
  register: UseFormRegister<TFormValues>;
  errors: FieldErrors<TFormValues>;
};

export function Field<TFormValues extends FieldValues>({
  name,
  label,
  type = "text",
  placeholder,
  autoComplete,
  register,
  errors
}: FieldProps<TFormValues>) {
  const error = errors[name];
  const errorId = name + "-error";

  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={name}
        type={type}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        className={
          "w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 " +
          (error ? "border-red-500" : "border-gray-300 focus:border-blue-500")
        }
        {...register(name)}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-red-600">
          {String(error.message ?? "This field is invalid")}
        </p>
      ) : null}
    </div>
  );
}

# =========================================================
# FILE: components/RegistrationForm.tsx
# =========================================================
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { Path } from "react-hook-form";

import { Field } from "./Field";
import {
  registrationBundleSchema,
  registrationFormSchema,
  type RegistrationBundleInput,
  type RegistrationFormFields
} from "../lib/validators";

type StepId = "account" | "address" | "confirm";

const STEPS: ReadonlyArray<{ id: StepId; label: string; fields: ReadonlyArray<keyof RegistrationFormFields> }> = [
  { id: "account", label: "Account", fields: ["email", "password", "confirmPassword"] },
  {
    id: "address",
    label: "Address",
    fields: ["fullName", "addressLine1", "addressLine2", "city", "zip", "country", "phone"]
  },
  { id: "confirm", label: "Confirm", fields: ["termsAccepted", "marketingOptIn"] }
];

type RegistrationFormProps = {
  onSubmitSuccess: (data: RegistrationFormFields) => void;
};

export function RegistrationForm({ onSubmitSuccess }: RegistrationFormProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const currentStep = STEPS[stepIndex];

  const {
    register,
    handleSubmit,
    trigger,
    setError,
    getValues,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<RegistrationFormFields>({
    mode: "onTouched",
    resolver: zodResolver(registrationFormSchema),
    defaultValues: {
      email: "",
      password: "",
      confirmPassword: "",
      fullName: "",
      addressLine1: "",
      addressLine2: "",
      city: "",
      zip: "",
      country: "",
      phone: "",
      termsAccepted: false,
      marketingOptIn: false
    }
  });

  async function handleNext(): Promise<void> {
    const stepFields = currentStep.fields as unknown as Path<RegistrationFormFields>[];
    const isValid = await trigger(stepFields);
    if (!isValid) {
      return;
    }
    setSubmissionError(null);
    setStepIndex((index) => Math.min(index + 1, STEPS.length - 1));
  }

  function handleBack(): void {
    setSubmissionError(null);
    setStepIndex((index) => Math.max(index - 1, 0));
  }

  async function submitForm(data: RegistrationFormFields): Promise<void> {
    const bundles: RegistrationBundleInput[] = [
      { step: "account", data },
      { step: "address", data },
      { step: "confirm", data }
    ];

    for (let index = 0; index < bundles.length; index += 1) {
      const result = registrationBundleSchema.safeParse(bundles[index]);
      if (result.success) {
        continue;
      }

      const failingStep = bundles[index].step;
      const failingStepIndex = STEPS.findIndex((step) => step.id === failingStep);

      for (const issue of result.error.issues) {
        const field = issue.path[0];
        if (typeof field === "string") {
          setError(field as keyof RegistrationFormFields, {
            type: "validate",
            message: issue.message
          });
        }
      }

      if (failingStepIndex >= 0) {
        setStepIndex(failingStepIndex);
      }
      setSubmissionError('Step "' + failingStep + '" failed final validation. Fix the field and submit again.');
      return;
    }

    setSubmissionError(null);
    onSubmitSuccess(data);
    reset();
  }

  return (
    <form
      onSubmit={handleSubmit(submitForm)}
      noValidate
      className="mx-auto max-w-xl space-y-8 p-6"
    >
      <div role="group" aria-label="Form progress">
        <ol className="flex items-center gap-2 text-sm">
          {STEPS.map((step, index) => (
            <li key={step.id} className="flex items-center gap-2">
              <span
                className={
                  index === stepIndex
                    ? "font-bold text-blue-600"
                    : index < stepIndex
                      ? "text-gray-500"
                      : "text-gray-400"
                }
              >
                {step.label}
              </span>
              {index < STEPS.length - 1 ? <span aria-hidden="true">/</span> : null}
            </li>
          ))}
        </ol>
      </div>

      {stepIndex === 0 ? (
        <fieldset className="space-y-4">
          <legend className="text-lg font-semibold">Account</legend>
          <Field
            name="email"
            label="Email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            register={register}
            errors={errors}
          />
          <Field
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            register={register}
            errors={errors}
          />
          <Field
            name="confirmPassword"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            register={register}
            errors={errors}
          />
        </fieldset>
      ) : null}

      {stepIndex === 1 ? (
        <fieldset className="space-y-4">
          <legend className="text-lg font-semibold">Address</legend>
          <Field name="fullName" label="Full name" autoComplete="name" register={register} errors={errors} />
          <Field
            name="addressLine1"
            label="Street address"
            autoComplete="address-line1"
            register={register}
            errors={errors}
          />
          <Field
            name="addressLine2"
            label="Apartment, suite (optional)"
            autoComplete="address-line2"
            register={register}
            errors={errors}
          />
          <Field name="city" label="City" autoComplete="address-level2" register={register} errors={errors} />
          <Field name="zip" label="Postal code" autoComplete="postal-code" register={register} errors={errors} />
          <Field
            name="phone"
            label="Phone"
            type="tel"
            placeholder="+1 555 123 4567"
            autoComplete="tel"
            register={register}
            errors={errors}
          />
          <div className="space-y-1">
            <label htmlFor="country" className="block text-sm font-medium">
              Country
            </label>
            <select
              id="country"
              {...register("country")}
              aria-invalid={Boolean(errors.country)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">Select a country</option>
              <option value="US">United States</option>
              <option value="GB">United Kingdom</option>
              <option value="DE">Germany</option>
              <option value="JP">Japan</option>
              <option value="KE">Kenya</option>
            </select>
            {errors.country ? (
              <p role="alert" className="text-sm text-red-600">
                {errors.country.message}
              </p>
            ) : null}
          </div>
        </fieldset>
      ) : null}

      {stepIndex === 2 ? (
        <fieldset className="space-y-4">
          <legend className="text-lg font-semibold">Confirm</legend>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              {...register("termsAccepted")}
              aria-invalid={Boolean(errors.termsAccepted)}
              className="mt-0.5"
            />
            <span>I accept the terms and conditions.</span>
          </label>
          {errors.termsAccepted ? (
            <p role="alert" className="text-sm text-red-600">
              {errors.termsAccepted.message}
            </p>
          ) : null}
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" {...register("marketingOptIn")} className="mt-0.5" />
            <span>Send me product updates (optional).</span>
          </label>
        </fieldset>
      ) : null}

      {submissionError ? <p role="alert">{submissionError}</p> : null}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={handleBack}
          disabled={stepIndex === 0}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm disabled:opacity-50"
        >
          Back
        </button>
        {stepIndex < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={handleNext}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white"
          >
            Next
          </button>
        ) : (
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            {isSubmitting ? "Submitting..." : "Create account"}
          </button>
        )}
      </div>
    </form>
  );
}

# =========================================================
# FILE: app/layout.tsx
# =========================================================
import type { ReactNode } from "react";

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

# =========================================================
# FILE: app/page.tsx
# =========================================================
"use client";

import { useState } from "react";
import { RegistrationForm } from "../components/RegistrationForm";
import type { RegistrationFormFields } from "../lib/validators";

export default function App() {
  const [lastRegistered, setLastRegistered] = useState<RegistrationFormFields | null>(null);

  return (
    <main className="min-h-screen py-10">
      <h1 className="text-center text-2xl font-bold">Create your account</h1>
      <RegistrationForm
        onSubmitSuccess={(data) => {
          setLastRegistered(data);
          console.log("Registered:", data.email, data.fullName);
        }}
      />
      {lastRegistered ? (
        <p className="mx-auto mt-8 max-w-xl text-center text-sm">
          Saved account for {lastRegistered.fullName} ({lastRegistered.email}) in {lastRegistered.country}.
        </p>
      ) : null}
    </main>
  );
}
```

## 4. Execution Protocol & Step-by-Step Workflow
```bash
# 1. Scaffold the project and install dependencies
mkdir form-validation-schema-builder
cd form-validation-schema-builder
npm install

# 2. Write lib/validators.ts (per-step schemas + full schema + discriminated union)
# 3. Write components/Field.tsx (generic typed wrapper)
# 4. Write components/RegistrationForm.tsx (3-step progressive form)
# 5. Write app/layout.tsx + app/page.tsx (App usage example)

# 6. Type-check and build
npm run typecheck
npm run build

# 7. Runtime verification
npm run dev
#    Open http://localhost:3000 and walk the flow:
#    - Leave Email empty -> "Email is required" on first blur (onTouched mode)
#    - Enter mismatched passwords -> "Passwords do not match" (superRefine)
#    - Enter "abc" as postal code -> regex failure on the Address step
#    - Skip the terms checkbox -> Confirm step blocks with a refine error
#    - Complete all steps -> discriminating safeParse passes, onSubmitSuccess fires
```

## 5. Edge Cases & Error Handling
- Validation before any interaction: `mode: "onTouched"` validates on first blur, not on keystrokes, so long fields (email) validate cleanly without premature error noise.
- Step gating: `handleNext` calls `trigger` with only the visible step's field names; advancing requires the current step to be valid and never re-validates hidden steps.
- Password confirmation parity: the `superRefine` issue is attached to the `confirmPassword` path so it renders inline like any field error, in both the account step schema and the full form schema.
- Discriminated-union final gate: `registrationBundleSchema.safeParse` re-checks each `{ step, data }` bundle on submit; the first failing step is jumped to, its issues are mapped back onto fields with `setError`, and submission is aborted before persistence.
- Cross-boundary consistency: `z.infer<typeof registrationFormSchema>` feeds the generic `<Field>`, the form state, and the `onSubmitSuccess` payload; changing any schema re-types every consumer at compile time.
- SSR hydration: the form and theme classes are inert on the server, but `getValues()`/`reset()` are only called in event handlers, so no read of unpinned browser state leaks into the initial render.
- Rollback: on schema contract changes, re-run `npm run typecheck` first; keep `lib/validators.ts` as the only place field rules live and regenerate `Field`/`RegistrationForm` from it instead of patching both files.