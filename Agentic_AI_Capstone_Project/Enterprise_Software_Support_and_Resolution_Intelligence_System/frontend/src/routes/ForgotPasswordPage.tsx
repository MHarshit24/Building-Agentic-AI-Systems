import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../api/endpoints";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { AuthLayout } from "../components/layout/AuthLayout";

const schema = z.object({ email: z.string().email("Enter a valid email address") });
type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    // Backend always returns the same generic 202 regardless of whether
    // the email exists (anti-enumeration) — the UI must never reveal that
    // distinction either, so this always shows the same success state.
    await requestPasswordReset(values);
    setSubmitted(true);
  };

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter your account email and we'll send you a reset link."
      footer={
        <Link to="/login" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
          Back to sign in
        </Link>
      }
    >
      {submitted ? (
        <p className="rounded-lg bg-green-50 p-3 text-sm text-green-800 dark:bg-green-900/30 dark:text-green-300">
          If an account exists for that email, a reset link has been sent.
        </p>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <Input
            label="Email"
            type="email"
            autoComplete="username"
            error={errors.email?.message}
            {...register("email")}
          />
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? <Spinner /> : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
