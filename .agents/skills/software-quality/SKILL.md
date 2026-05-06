---
name: software-quality
description: Orienta a obrigatoriedade de criação de testes automatizados e o seguimento rigoroso dos princípios SOLID e de inversão de dependência em qualquer código desenvolvido ou refatorado. Use esta skill sempre que estiver escrevendo código para garantir alta qualidade.
---

# Software Quality

Ao desenvolver ou refatorar qualquer código neste projeto, você deve SEMPRE aderir às seguintes diretrizes de qualidade de software:

## 1. Testes Automatizados Obrigatórios
- Para cada nova funcionalidade, alteração de comportamento ou correção de bug, você DEVE criar ou atualizar os testes automatizados correspondentes (testes unitários e/ou de integração).
- O código só é considerado concluído quando estiver coberto por testes que validem seu comportamento.

## 2. Princípios SOLID
Aplique rigorosamente os 5 princípios SOLID em todo o design e implementação de código:
- **S**ingle Responsibility: Cada classe ou módulo deve ter um, e apenas um, motivo para mudar.
- **O**pen/Closed: Entidades de software devem estar abertas para extensão, mas fechadas para modificação.
- **L**iskov Substitution: Objetos em um programa devem ser substituíveis por instâncias de seus subtipos sem alterar a corretude do programa.
- **I**nterface Segregation: Muitas interfaces específicas para clientes são melhores do que uma interface de propósito geral.
- **D**ependency Inversion: Dependa de abstrações e não de implementações concretas (veja o próximo tópico).

## 3. Inversão e Injeção de Dependência
- A comunicação entre diferentes componentes (ex: Controladores, Serviços, DAO/Repositórios) deve ocorrer através de abstrações (ex: ABCs ou Protocols em Python).
- Módulos de alto nível não devem importar diretamente ou instanciar módulos de baixo nível. Em vez disso, injete as dependências necessárias através de construtores.
- Esta prática garante o baixo acoplamento e é fundamental para permitir a criação de *mocks* e *stubs* eficientes durante os testes automatizados.
