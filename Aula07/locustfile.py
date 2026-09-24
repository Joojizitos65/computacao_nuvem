from locust import HttpUser, task, between


class AlunoRadarEnem(HttpUser):
    wait_time = between(1, 3)

    @task
    def calcular_nota(self):
        payload = {"notas": [720.5, 680.0, 810.2, 640.8, 780.0]}
        self.client.post("/api/CalculaNota", json=payload)
