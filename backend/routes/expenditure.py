from fastapi import APIRouter
from bson import ObjectId
from datetime import datetime
from fastapi import HTTPException
from models.expenditure import Expenditure

router = APIRouter(prefix="/api/expenditures", tags=["Expenditures"])

# This variable will be assigned from server.py
expenditures_collection = None


@router.post("/")
async def add_expenditure(expense: Expenditure):

    data = expense.model_dump()

    result = await expenditures_collection.insert_one(data)

    return {
        "success": True,
        "message": "Expenditure Added Successfully",
        "id": str(result.inserted_id)
    }


@router.get("/")
async def get_expenditures():

    expenses = []

    async for item in expenditures_collection.find().sort("date", -1):

        item["_id"] = str(item["_id"])

        expenses.append(item)

    return expenses
@router.delete("/{expense_id}")
async def delete_expenditure(expense_id: str):

    result = await expenditures_collection.delete_one(
        {"_id": ObjectId(expense_id)}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    return {
        "success": True,
        "message": "Expense Deleted Successfully"
    }

@router.put("/{expense_id}")
async def update_expenditure(expense_id: str, expense: Expenditure):

    result = await expenditures_collection.update_one(
        {"_id": ObjectId(expense_id)},
        {
            "$set": expense.model_dump()
        }
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    return {
        "success": True,
        "message": "Expense Updated Successfully"
    }