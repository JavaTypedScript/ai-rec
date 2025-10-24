# How to run this application

## Make 3 terminals
```
cd Backend/back2
```
```
cd Backend/back2
```
```
cd frontend/ai-rec
```

## In first terminal run(uvicorn terminal (api))
```
pip install -r requirements.txt
```

## In third terminal run(frontend/ai-rec)
```
npm init -y
npm i

```
## Running the application

### In first terminal(uvicorn)
```
uvicorn saas_api:app --reload
```

### In second terminal(mlflow)
```
mlflow ui --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlflow_artifacts

```
### In third terminal(frontend)
```
npm run dev
```

## Go to localhost:5173 or frontend luanched port, to view mlflow go to localhost:5000

## Upload dataset(if not with you, use datasets in example_dataset folder) and enter into required fields,select ready model and select required fields and click get recommendations

# Finally Peace
