import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AxiosError } from "axios";
import { Link, useNavigate } from "react-router-dom";
import { register as registerAccount } from "../api/endpoints";
import { useAuthStore } from "../store/authStore";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { AuthLayout } from "../components/layout/AuthLayout";

const schema = z
  .object({
    email: z.string().email("Enter a valid email address"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });
type FormValues = z.infer<typeof schema>;

export default function SignUpPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register: registerField,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const res = await registerAccount({ email: values.email, password: values.password });
      setSession(res.access_token, res.refresh_token, res.role);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 409) {
        setServerError("An account with this email already exists.");
      } else {
        setServerError("Something went wrong creating your account. Please try again.");
      }
    }
  };

  return (
    <AuthLayout
      title="Create an account"
      subtitle="New accounts are created as Support Agent — an admin can upgrade your role later."
      footer={
        <>
          <span className="text-slate-500 dark:text-slate-400">Already have an account? </span>
          <Link to="/login" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
            Sign in
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          error={errors.email?.message}
          {...registerField("email")}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          error={errors.password?.message}
          {...registerField("password")}
        />
        <Input
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirmPassword?.message}
          {...registerField("confirmPassword")}
        />
        {serverError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {serverError}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? <Spinner /> : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}
