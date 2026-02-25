"""HTTP clients for Volcengine ASR/LLM/Video endpoints."""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from app.schemas.config import ASRConfig, LLMConfig, VideoConfig


class VolcAPIError(RuntimeError):
    pass


def _deep_find(data: Any, keys: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys:
                found.append(v)
            found.extend(_deep_find(v, keys))
    elif isinstance(data, list):
        for item in data:
            found.extend(_deep_find(item, keys))
    return found


def _first_string(values: list[Any]) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_asr_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        direct = result.get("text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

    utterances = _deep_find(payload, {"utterances", "sentences"})
    for block in utterances:
        if isinstance(block, list):
            parts: list[str] = []
            for row in block:
                if isinstance(row, dict):
                    text = row.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)

    candidates = _deep_find(payload, {"text"})
    direct = _first_string(candidates)
    if direct:
        return direct

    return ""


def parse_llm_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
            content = first.get("content")
            if isinstance(content, str):
                return content.strip()

    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    candidates = _deep_find(payload, {"text", "content"})
    content = _first_string(candidates)
    return content or ""


def extract_first_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty llm output")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("no json object found in llm output")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("llm output json must be object")
    return parsed


class ASRClient:
    _RESOURCE_FALLBACKS = ("volc.bigasr.auc_turbo", "volc.seedasr.auc", "volc.bigasr.auc")
    _STANDARD_PROCESSING_STATUS = {"20000001"}
    _STANDARD_TERMINAL_STATUS = {"20000000", "20000003"}

    @staticmethod
    def _is_grant_not_found_error(response: httpx.Response) -> bool:
        text_lower = response.text.lower()
        if "requested grant not found" in text_lower:
            return True
        try:
            payload = response.json()
        except Exception:
            return False
        header = payload.get("header")
        if not isinstance(header, dict):
            return False
        message = str(header.get("message", "")).lower()
        return "grant" in message and "not found" in message

    @staticmethod
    def _is_resource_not_allowed_error(response: httpx.Response) -> bool:
        text_lower = response.text.lower()
        if "resourceid" in text_lower and "not allowed" in text_lower:
            return True
        try:
            payload = response.json()
        except Exception:
            return False
        header = payload.get("header")
        if not isinstance(header, dict):
            return False
        message = str(header.get("message", "")).lower()
        return "resourceid" in message and "not allowed" in message

    @staticmethod
    def _is_resource_not_granted_error(response: httpx.Response) -> bool:
        text_lower = response.text.lower()
        if "requested resource not granted" in text_lower:
            return True
        if "resource_id=" in text_lower and "not granted" in text_lower:
            return True
        try:
            payload = response.json()
        except Exception:
            return False
        header = payload.get("header")
        if not isinstance(header, dict):
            return False
        message = str(header.get("message", "")).lower()
        return "resource" in message and "not granted" in message

    @staticmethod
    def _is_permission_message(message: str) -> bool:
        text = message.lower()
        patterns = (
            "requested grant not found",
            "resourceid",
            "not allowed",
            "requested resource not granted",
            "not granted",
        )
        return all(part in text for part in ("resourceid", "not allowed")) or any(p in text for p in patterns)

    @staticmethod
    def _extract_reqid(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return ""
        header = payload.get("header")
        if isinstance(header, dict):
            reqid = header.get("reqid")
            if isinstance(reqid, str):
                return reqid
        return ""

    @staticmethod
    def _extract_status_code(response: httpx.Response) -> str:
        status = response.headers.get("X-Api-Status-Code")
        if status:
            return str(status)
        try:
            payload = response.json()
        except Exception:
            return ""
        header = payload.get("header")
        if isinstance(header, dict):
            code = header.get("code")
            if code is not None:
                return str(code)
        return ""

    @staticmethod
    def _extract_status_message(response: httpx.Response) -> str:
        message = response.headers.get("X-Api-Message")
        if message:
            return str(message)
        try:
            payload = response.json()
        except Exception:
            return ""
        header = payload.get("header")
        if isinstance(header, dict):
            msg = header.get("message")
            if msg is not None:
                return str(msg)
        return ""

    @staticmethod
    def _guess_audio_format(audio_file: Path) -> str:
        suffix = audio_file.suffix.lower().lstrip(".")
        if suffix:
            return suffix
        return "wav"

    def _build_headers(self, cfg: ASRConfig, *, resource_id: str, request_id: Optional[str] = None) -> dict[str, str]:
        return {
            "X-Api-App-Key": cfg.appid,
            "X-Api-Access-Key": cfg.access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id or str(uuid.uuid4()),
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }

    def _is_permission_response(self, response: httpx.Response) -> bool:
        return (
            self._is_grant_not_found_error(response)
            or self._is_resource_not_allowed_error(response)
            or self._is_resource_not_granted_error(response)
            or self._is_permission_message(response.text)
            or self._is_permission_message(self._extract_status_message(response))
        )

    @staticmethod
    def _append_try_error(
        errors: list[str],
        *,
        stage: str,
        resource_id: str,
        response: httpx.Response,
    ) -> None:
        reqid = ""
        try:
            payload = response.json()
            header = payload.get("header")
            if isinstance(header, dict):
                reqid = str(header.get("reqid", ""))
        except Exception:
            pass
        status_code = response.headers.get("X-Api-Status-Code", "")
        status_message = response.headers.get("X-Api-Message", "")
        errors.append(
            f"{stage}:{resource_id}:http={response.status_code}:status={status_code}:"
            f"reqid={reqid}:msg={status_message or response.text[:180]}"
        )

    def _post_flash_once(
        self,
        cfg: ASRConfig,
        *,
        url: str,
        audio_b64: str,
        resource_id: str,
    ) -> httpx.Response:
        headers = self._build_headers(cfg, resource_id=resource_id)
        payload: dict[str, Any] = {
            "user": {"uid": cfg.appid},
            "audio": {"data": audio_b64},
            "request": {"model_name": "bigmodel"},
        }
        if cfg.boosting_table_name:
            payload["request"]["boosting_table_name"] = cfg.boosting_table_name

        with httpx.Client(timeout=cfg.timeout_s) as client:
            return client.post(url, headers=headers, json=payload)

    def _post_standard_submit(
        self,
        cfg: ASRConfig,
        *,
        url: str,
        audio_b64: str,
        audio_format: str,
        resource_id: str,
        request_id: str,
    ) -> httpx.Response:
        headers = self._build_headers(cfg, resource_id=resource_id, request_id=request_id)
        payload: dict[str, Any] = {
            "user": {"uid": cfg.appid},
            "audio": {"data": audio_b64, "format": audio_format},
            "request": {"model_name": "bigmodel"},
        }
        if cfg.boosting_table_name:
            payload["request"]["boosting_table_name"] = cfg.boosting_table_name

        with httpx.Client(timeout=cfg.timeout_s) as client:
            return client.post(url, headers=headers, json=payload)

    def _post_standard_query(
        self,
        cfg: ASRConfig,
        *,
        url: str,
        resource_id: str,
        request_id: str,
    ) -> httpx.Response:
        headers = self._build_headers(cfg, resource_id=resource_id, request_id=request_id)
        with httpx.Client(timeout=cfg.timeout_s) as client:
            return client.post(url, headers=headers, json={})

    def _candidate_resource_ids(self, cfg: ASRConfig) -> list[str]:
        candidates: list[str] = []
        configured = (cfg.resource_id or "").strip()
        if configured:
            candidates.append(configured)
        for fallback in self._RESOURCE_FALLBACKS:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def _recognize_flash(
        self,
        cfg: ASRConfig,
        *,
        candidate_resource_ids: list[str],
        audio_b64: str,
        tried_errors: list[str],
    ) -> Optional[dict[str, Any]]:
        base = cfg.base_url.rstrip("/")
        url = f"{base}/api/v3/auc/bigmodel/recognize/flash"
        for resource_id in candidate_resource_ids:
            resp = self._post_flash_once(cfg, url=url, audio_b64=audio_b64, resource_id=resource_id)
            if resp.status_code >= 400:
                self._append_try_error(tried_errors, stage="flash", resource_id=resource_id, response=resp)
                if self._is_permission_response(resp):
                    continue
                raise VolcAPIError(f"ASR request failed: {resp.status_code} {resp.text[:500]}")

            status_code = self._extract_status_code(resp)
            if status_code and status_code != "20000000":
                self._append_try_error(tried_errors, stage="flash", resource_id=resource_id, response=resp)
                if self._is_permission_message(self._extract_status_message(resp)):
                    continue
                raise VolcAPIError(
                    f"ASR business error: {status_code} {self._extract_status_message(resp)} {resp.text[:500]}"
                )

            payload_json = resp.json()
            header = payload_json.get("header")
            if isinstance(header, dict):
                business_code = header.get("code")
                if business_code not in (None, 20000000, "20000000"):
                    message = str(header.get("message", ""))
                    if self._is_permission_message(message):
                        self._append_try_error(tried_errors, stage="flash", resource_id=resource_id, response=resp)
                        continue
                    raise VolcAPIError(f"ASR business error: {business_code} {message} {resp.text[:500]}")
            return payload_json
        return None

    def _recognize_standard(
        self,
        cfg: ASRConfig,
        *,
        audio_file: Path,
        audio_b64: str,
        candidate_resource_ids: list[str],
        tried_errors: list[str],
    ) -> Optional[dict[str, Any]]:
        base = cfg.base_url.rstrip("/")
        submit_url = f"{base}/api/v3/auc/bigmodel/submit"
        query_url = f"{base}/api/v3/auc/bigmodel/query"
        audio_format = self._guess_audio_format(audio_file)

        for resource_id in candidate_resource_ids:
            request_id = str(uuid.uuid4())
            submit_resp = self._post_standard_submit(
                cfg,
                url=submit_url,
                audio_b64=audio_b64,
                audio_format=audio_format,
                resource_id=resource_id,
                request_id=request_id,
            )
            if submit_resp.status_code >= 400:
                self._append_try_error(tried_errors, stage="submit", resource_id=resource_id, response=submit_resp)
                if self._is_permission_response(submit_resp):
                    continue
                raise VolcAPIError(f"ASR submit failed: {submit_resp.status_code} {submit_resp.text[:500]}")

            submit_status = self._extract_status_code(submit_resp)
            if submit_status and submit_status != "20000000":
                self._append_try_error(tried_errors, stage="submit", resource_id=resource_id, response=submit_resp)
                submit_message = self._extract_status_message(submit_resp)
                if self._is_permission_message(submit_message):
                    continue
                raise VolcAPIError(
                    f"ASR submit business error: {submit_status} {submit_message} {submit_resp.text[:500]}"
                )

            deadline = time.time() + max(5, cfg.timeout_s)
            while time.time() < deadline:
                query_resp = self._post_standard_query(
                    cfg,
                    url=query_url,
                    resource_id=resource_id,
                    request_id=request_id,
                )
                if query_resp.status_code >= 400:
                    self._append_try_error(tried_errors, stage="query", resource_id=resource_id, response=query_resp)
                    if self._is_permission_response(query_resp):
                        break
                    raise VolcAPIError(f"ASR query failed: {query_resp.status_code} {query_resp.text[:500]}")

                query_status = self._extract_status_code(query_resp)
                if query_status in self._STANDARD_PROCESSING_STATUS:
                    time.sleep(1)
                    continue
                if query_status in self._STANDARD_TERMINAL_STATUS or not query_status:
                    return query_resp.json()

                query_message = self._extract_status_message(query_resp)
                self._append_try_error(tried_errors, stage="query", resource_id=resource_id, response=query_resp)
                if self._is_permission_message(query_message):
                    break
                raise VolcAPIError(
                    f"ASR query business error: {query_status} {query_message} {query_resp.text[:500]}"
                )
            else:
                raise VolcAPIError(f"ASR standard query timed out after {cfg.timeout_s}s (resource_id={resource_id})")

        return None

    def recognize(self, cfg: ASRConfig, audio_file: Path) -> dict[str, Any]:
        if not cfg.appid or not cfg.access_token:
            raise VolcAPIError("ASR appid/access_token is required")

        candidate_resource_ids = self._candidate_resource_ids(cfg)
        audio_b64 = base64.b64encode(audio_file.read_bytes()).decode("utf-8")
        tried_errors: list[str] = []
        flash_payload = self._recognize_flash(
            cfg,
            candidate_resource_ids=candidate_resource_ids,
            audio_b64=audio_b64,
            tried_errors=tried_errors,
        )
        if flash_payload is not None:
            return flash_payload

        standard_payload = self._recognize_standard(
            cfg,
            audio_file=audio_file,
            audio_b64=audio_b64,
            candidate_resource_ids=candidate_resource_ids,
            tried_errors=tried_errors,
        )
        if standard_payload is not None:
            return standard_payload

        tried = ",".join(candidate_resource_ids)
        details = " | ".join(tried_errors)[:1400]
        raise VolcAPIError(
            "ASR resource is not granted for current credentials. "
            f"Tried resource_id(s): {tried}. "
            f"Details: {details}. "
            "Please use an ASR app/token with granted resourceId from Volcengine Speech Console."
        )


class LLMClient:
    def generate_text(
        self,
        cfg: LLMConfig,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> tuple[str, dict[str, Any]]:
        base = cfg.base_url.rstrip("/")
        url = f"{base}/api/v3/chat/completions"
        payload = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": cfg.temperature if temperature is None else temperature,
        }
        headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=cfg.timeout_s) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise VolcAPIError(f"LLM request failed: {resp.status_code} {resp.text[:500]}")

        payload_json = resp.json()
        return parse_llm_text(payload_json), payload_json


class VideoClient:
    @staticmethod
    def _submit_payload_candidates(
        cfg: VideoConfig,
        *,
        prompt: str,
        duration_s: int,
        width: int,
        height: int,
    ) -> list[dict[str, Any]]:
        duration = max(1, int(duration_s))
        safe_width = max(1, int(width))
        safe_height = max(1, int(height))
        content = [{"type": "text", "text": prompt}]

        # Prefer Ark content schema; keep legacy payload as final fallback.
        return [
            {
                "model": cfg.model,
                "content": content,
                "duration": duration,
                "width": safe_width,
                "height": safe_height,
            },
            {
                "model": cfg.model,
                "content": content,
                "duration": duration,
                "size": f"{safe_width}x{safe_height}",
            },
            {
                "model": cfg.model,
                "content": content,
                "duration": duration,
            },
            {
                "model": cfg.model,
                "content": content,
            },
            {
                "model": cfg.model,
                "prompt": prompt,
                "duration": duration,
                "resolution": f"{safe_width}x{safe_height}",
            },
        ]

    def submit_generation(
        self,
        cfg: VideoConfig,
        *,
        prompt: str,
        duration_s: int,
        width: int,
        height: int,
    ) -> tuple[str, dict[str, Any]]:
        base = cfg.base_url.rstrip("/")
        url = f"{base}/api/v3/contents/generations/tasks"
        headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
        attempt_errors: list[str] = []
        payload_candidates = self._submit_payload_candidates(
            cfg,
            prompt=prompt,
            duration_s=duration_s,
            width=width,
            height=height,
        )

        with httpx.Client(timeout=cfg.timeout_s) as client:
            for idx, payload in enumerate(payload_candidates, start=1):
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    attempt_errors.append(f"attempt={idx}:http={resp.status_code}:msg={resp.text[:220]}")
                    # Parameter-shape mismatch can be retried with next payload template.
                    if resp.status_code in (400, 422):
                        continue
                    raise VolcAPIError(f"Video submit failed: {resp.status_code} {resp.text[:500]}")

                data = resp.json()
                task_id_candidates = _deep_find(data, {"task_id", "id"})
                task_id = _first_string(task_id_candidates)
                if task_id:
                    return task_id, data

                attempt_errors.append(f"attempt={idx}:http={resp.status_code}:missing_task_id")

        details = " | ".join(attempt_errors)[:1200]
        raise VolcAPIError(f"Video submit failed after payload fallbacks. {details}")

    def poll_until_done(
        self,
        cfg: VideoConfig,
        task_id: str,
        timeout_s: Optional[int] = None,
    ) -> dict[str, Any]:
        base = cfg.base_url.rstrip("/")
        url = f"{base}/api/v3/contents/generations/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}

        effective_timeout = timeout_s or cfg.timeout_s
        deadline = time.time() + effective_timeout
        interval = max(1, int(cfg.poll_interval_s))

        with httpx.Client(timeout=max(30, interval + 10)) as client:
            while True:
                resp = client.get(url, headers=headers)
                if resp.status_code >= 400:
                    raise VolcAPIError(f"Video polling failed: {resp.status_code} {resp.text[:500]}")

                payload = resp.json()
                status_candidates = _deep_find(payload, {"status", "state"})
                status = (_first_string(status_candidates) or "").lower()

                if status in {"succeeded", "success", "completed", "done"}:
                    return payload
                if status in {"failed", "error", "canceled", "cancelled"}:
                    raise VolcAPIError(f"Video generation failed: status={status}")

                if time.time() > deadline:
                    raise VolcAPIError("Video generation timed out")

                time.sleep(interval)

    def extract_video_url(self, payload: dict[str, Any]) -> str:
        url_candidates = _deep_find(payload, {"video_url", "url", "output_url", "file_url", "download_url"})
        url_value = _first_string(url_candidates)
        if not url_value:
            raise VolcAPIError("Video result missing downloadable URL")
        return url_value

    def download_video(self, url: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=180) as resp:
            resp.raise_for_status()
            with output_path.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
