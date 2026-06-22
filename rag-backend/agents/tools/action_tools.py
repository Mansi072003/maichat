# agents/tools/action_tools.py
"""
Action tools for the Action Agent (maiaction).

These tools perform real actions (or stage them for confirmation):
  createAppointment    — book / request an appointment
  sendCommunication    — send a message to clinic / provider
  createTask           — create a follow-up reminder or task
  escalateToClinician  — escalate a critical result or urgent request

FHIR Resource Mapping (target state for each tool):
  createAppointment   → Appointment (status=proposed) + Slot
  sendCommunication   → Communication (status=in-progress, medium=electronic)
  createTask          → Task (status=requested, intent=order)
  escalateToClinician → Flag (status=active, category=safety) + Task (priority=urgent)
"""
from typing import Dict, Any, Optional
from datetime import datetime
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class CreateAppointment(BaseTool):
    name = "createAppointment"
    description = "Request or book an appointment for a patient. Returns a confirmation or pending status."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"},
            "reason": {"type": "string", "description": "Reason for the appointment"},
            "preferredDate": {"type": "string", "description": "Optional: preferred date (YYYY-MM-DD)"},
            "department": {"type": "string", "description": "Optional: department or specialty"},
        },
        "required": ["patientId", "reason"]
    }

    def __init__(self, mongodb_service):
        self.mongodb_service = mongodb_service

    async def execute(self, patientId: str, reason: str, preferredDate: str = None, department: str = None, **kwargs) -> Dict[str, Any]:
        try:
            request_data = {
                "type": "appointment_request",
                "patientId": patientId,
                "reason": reason,
                "preferredDate": preferredDate,
                "department": department,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }
            await self.mongodb_service.set_json("action_requests", f"appt-{patientId}-{datetime.utcnow().timestamp()}", request_data)
            return {
                "status": "pending",
                "message": f"Appointment request submitted for {reason}. The clinic will confirm your appointment shortly.",
                "details": request_data,
            }
        except Exception as e:
            logger.error(f"createAppointment error: {e}")
            return {"status": "error", "message": str(e)}


class SendCommunication(BaseTool):
    name = "sendCommunication"
    description = "Send a message to the clinic, provider, or care team on behalf of the patient."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"},
            "recipient": {"type": "string", "description": "Who to send to (e.g. 'care_team', 'nurse', 'doctor', 'pharmacy')"},
            "message": {"type": "string", "description": "The message content"},
            "priority": {"type": "string", "description": "Optional: priority level (normal, urgent). Default: normal"},
        },
        "required": ["patientId", "recipient", "message"]
    }

    def __init__(self, mongodb_service):
        self.mongodb_service = mongodb_service

    async def execute(self, patientId: str, recipient: str, message: str, priority: str = "normal", **kwargs) -> Dict[str, Any]:
        try:
            comm_data = {
                "type": "communication",
                "patientId": patientId,
                "recipient": recipient,
                "message": message,
                "priority": priority,
                "status": "sent",
                "created_at": datetime.utcnow().isoformat(),
            }
            await self.mongodb_service.set_json("action_requests", f"comm-{patientId}-{datetime.utcnow().timestamp()}", comm_data)
            return {
                "status": "sent",
                "message": f"Message sent to {recipient}. They will respond during business hours.",
                "details": comm_data,
            }
        except Exception as e:
            logger.error(f"sendCommunication error: {e}")
            return {"status": "error", "message": str(e)}


class CreateTask(BaseTool):
    name = "createTask"
    description = "Create a follow-up reminder or task for the patient or care team."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"},
            "taskDescription": {"type": "string", "description": "What needs to be done"},
            "dueDate": {"type": "string", "description": "Optional: when it should be completed (YYYY-MM-DD)"},
            "assignedTo": {"type": "string", "description": "Optional: who should do it (patient, nurse, doctor)"},
        },
        "required": ["patientId", "taskDescription"]
    }

    def __init__(self, mongodb_service):
        self.mongodb_service = mongodb_service

    async def execute(self, patientId: str, taskDescription: str, dueDate: str = None, assignedTo: str = "patient", **kwargs) -> Dict[str, Any]:
        try:
            task_data = {
                "type": "task",
                "patientId": patientId,
                "description": taskDescription,
                "dueDate": dueDate,
                "assignedTo": assignedTo,
                "status": "open",
                "created_at": datetime.utcnow().isoformat(),
            }
            await self.mongodb_service.set_json("action_requests", f"task-{patientId}-{datetime.utcnow().timestamp()}", task_data)
            return {
                "status": "created",
                "message": f"Reminder created: {taskDescription}",
                "details": task_data,
            }
        except Exception as e:
            logger.error(f"createTask error: {e}")
            return {"status": "error", "message": str(e)}


class EscalateToClinician(BaseTool):
    name = "escalateToClinician"
    description = "Escalate an urgent situation to a clinician: critical lab result, dangerous symptoms, or safety concern."
    parameters = {
        "type": "object",
        "properties": {
            "patientId": {"type": "string", "description": "The patient identifier"},
            "reason": {"type": "string", "description": "Why this needs escalation"},
            "urgency": {"type": "string", "description": "Urgency level: critical, urgent, routine"},
            "context": {"type": "string", "description": "Optional: additional context for the clinician"},
        },
        "required": ["patientId", "reason", "urgency"]
    }

    def __init__(self, mongodb_service):
        self.mongodb_service = mongodb_service

    async def execute(self, patientId: str, reason: str, urgency: str = "urgent", context: str = "", **kwargs) -> Dict[str, Any]:
        try:
            escalation_data = {
                "type": "escalation",
                "patientId": patientId,
                "reason": reason,
                "urgency": urgency,
                "context": context,
                "status": "escalated",
                "created_at": datetime.utcnow().isoformat(),
            }
            await self.mongodb_service.set_json("action_requests", f"esc-{patientId}-{datetime.utcnow().timestamp()}", escalation_data)
            logger.warning(f"ESCALATION [{urgency}] for {patientId}: {reason}")
            return {
                "status": "escalated",
                "message": f"This has been escalated to the care team with {urgency} priority.",
                "details": escalation_data,
            }
        except Exception as e:
            logger.error(f"escalateToClinician error: {e}")
            return {"status": "error", "message": str(e)}


def create_action_tools(mongodb_service):
    """Factory function to create all action tools."""
    return [
        CreateAppointment(mongodb_service),
        SendCommunication(mongodb_service),
        CreateTask(mongodb_service),
        EscalateToClinician(mongodb_service),
    ]
